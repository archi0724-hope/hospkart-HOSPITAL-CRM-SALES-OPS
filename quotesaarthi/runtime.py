from __future__ import annotations

import os
import re
import secrets
from copy import copy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from threading import RLock
from time import monotonic

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .agent import HospKartAgent
from .rag import HospKartRAG


class QuoteSaarthiAgent(HospKartAgent):
    """Retain handover searches/workflows with explicit draft pricing and tax."""

    def _parse_workflow_updates(self, query):
        updates=super()._parse_workflow_updates(query)
        explicit,_=self._extract_invoice_field_updates(query)
        if re.search(r'\b(?:discount|off)\b',query,re.I):
            updates['discount_percent']=str(self._extract_discount(query)*100)
        elif 'discount_percent' not in explicit:
            updates.pop('discount_percent',None)
        gst=re.search(r'\bgst\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*%|(?<![\w.])(-?\d+(?:\.\d+)?)\s*%\s*gst\b',query,re.I)
        if gst:
            updates['gst_rate_percent']=gst.group(1) or gst.group(2)
        return updates

    def _assign_workflow_value(self, flow_data, key, value):
        if key in {'quantity','discount_percent','gst_rate_percent'}:
            try:
                number=Decimal(str(value).strip().rstrip('%'))
            except InvalidOperation as error:
                raise ValueError('Valid numeric quantity, discount ya GST rate bhejein.') from error
            limit=1000000 if key=='quantity' else 100
            minimum=1 if key=='quantity' else 0
            if not number.is_finite() or not minimum<=number<=limit or (key=='quantity' and number!=number.to_integral()):
                raise ValueError('Quantity positive whole number; discount aur GST 0–100% hone chahiye.')
            value=str(number)
        super()._assign_workflow_value(flow_data,key,value)

    def _extract_quantity(self, query):
        match=re.search(r'\b(?:qty|quantity)\s*[:=]?\s*(-?\d+)\b|(?<![\w.])(-?\d+)\s*(?:units?|qty|quantity|pieces?|pcs?)\b',query,re.I)
        return int(match.group(1) or match.group(2)) if match else super()._extract_quantity(query)

    def _extract_discount(self, query):
        match=re.search(r'(-?\d+(?:\.\d+)?)\s*%\s*(?:discount|off)\b|\bdiscount\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*%',query,re.I)
        return float(match.group(1) or match.group(2))/100 if match else 0.0

    def search(self, query, top_k=5, options=None):
        original=self.rag
        active=bool(re.search(r'\bactive\s+vendors?\b|\bvendors?\s+active\b',query,re.I))
        available=bool(re.search(r'\bin[- ]stock\b|\bstock\s*0\b.*(?:hata|remove|exclude)|\bavailable\s+(?:stock|vendors?)\b',query,re.I))
        if active or available:
            filtered=copy(original)
            rows=original.products_df
            if active:
                rows=rows[rows['vendor_status'].astype(str).str.lower().eq('active')] if 'vendor_status' in rows else rows.iloc[:0]
            if available:
                rows=rows[rows['stock']>0] if 'stock' in rows else rows.iloc[:0]
            filtered.products_df=rows
            self.rag=filtered
            selected=self.state.last_selected_product
            if selected and not original._match_entities(query).get('products'):
                query=str(selected['product_name'])+' '+query
        try:
            return super().search(query,top_k,options)
        finally:
            self.rag=original

    def generate_quotation(self, query, selected_override=None):
        product_query=self._strip_invoice_control_segments(query)
        quantity=self._extract_quantity(product_query)
        if quantity is None or not 1<=quantity<=1000000:
            raise ValueError('Quantity confirm karein: example 50 units (1–1,000,000).')
        updates,_=self._extract_invoice_field_updates(query)
        preferences={**self.state.invoice_preferences,**updates}
        gst=re.search(r'\bgst\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*%|(?<![\w.])(-?\d+(?:\.\d+)?)\s*%\s*gst\b',query,re.I)
        if gst:
            preferences['gst_rate_percent']=gst.group(1) or gst.group(2)
        if 'gst_rate_percent' not in preferences:
            raise ValueError('GST rate confirm karein, example: GST 5% ya GST 18%. Catalogue se tax rate assume nahi kiya jayega.')
        try:
            tax=Decimal(str(preferences['gst_rate_percent']))
            discount=Decimal(str(self._extract_discount(product_query)))
        except InvalidOperation as error:
            raise ValueError('GST aur discount valid numbers hone chahiye.') from error
        if not tax.is_finite() or not 0<=tax<=100 or not discount.is_finite() or not 0<=discount<=1:
            raise ValueError('GST aur discount 0% se 100% ke beech hone chahiye.')
        selected=selected_override or self._select_product(product_query)
        if not selected:
            raise ValueError('Matching product nahi mila. Pehle catalogue mein product search karein.')
        unit=Decimal(str(selected.get('price',0)))
        if not unit.is_finite() or unit<=0:
            raise ValueError('Is product ka verified catalogue price available nahi hai.')
        self.state.invoice_preferences=preferences
        quote=super().generate_quotation(query,selected_override=selected)
        cents=Decimal('0.01')
        unit=unit.quantize(cents,rounding=ROUND_HALF_UP)
        subtotal=unit*quantity
        reduction=(subtotal*discount).quantize(cents,rounding=ROUND_HALF_UP)
        taxable=subtotal-reduction
        gst_amount=(taxable*tax/100).quantize(cents,rounding=ROUND_HALF_UP)
        quote.update(quantity=quantity,unit_price=float(unit),subtotal=float(subtotal),discount_amount=float(reduction),taxable_amount=float(taxable),gst_amount=float(gst_amount),final_amount=float(taxable+gst_amount),gst_rate=float(tax/100),document_type='draft_quotation',gst_rate_source='user_confirmed',draft=True)
        quote['vendor_name']=selected.get('vendor_name','Not provided')
        self.state.last_vendor_offers=self.rag.query_catalog(str(selected['product_name']),max_products=1,max_offers_per_product=25)['blocks']
        return quote

    def _render_quotation_text_template(self, quote, json_file, pdf_file):
        return '\n'.join([
            'DRAFT QUOTATION — QuoteSaarthi',f"Quotation ID: {quote['quote_id']}",
            f"Product: {quote['product_name']}",f"Vendor: {quote['vendor_name']}",
            f"Quantity: {quote['quantity']}",f"Unit Price: INR {quote['unit_price']:.2f}",
            f"Subtotal: INR {quote['subtotal']:.2f}",f"Discount: INR {quote['discount_amount']:.2f}",
            f"Taxable Amount: INR {quote['taxable_amount']:.2f}",
            f"GST ({quote['gst_rate']*100:g}%, user confirmed): INR {quote['gst_amount']:.2f}",
            f"Final Amount: INR {quote['final_amount']:.2f}",
            'Verify GST, stock, delivery and commercial terms before sending. This is a draft, not an issued tax invoice.',
            f'JSON Export: {json_file}',f'PDF Export: {pdf_file}'
        ])

    def export_quotation_pdf(self, quote):
        target=self.exports_dir/f"{quote['quote_id']}.pdf"
        pdf=canvas.Canvas(str(target),pagesize=A4)
        pdf.setTitle('QuoteSaarthi draft quotation')
        text=self._render_quotation_text_template(quote,'','').split('JSON Export:')[0]
        y=800
        for line in text.splitlines():
            for wrapped in self._split_text_lines(line,88):
                if y<50:
                    pdf.showPage();y=800
                pdf.setFont('Helvetica',10)
                pdf.drawString(40,y,wrapped.replace('—','-'));y-=17
        pdf.save()
        return target

    def _smalltalk_reply(self, query):
        reply=super()._smalltalk_reply(query)
        return reply.replace('QuoteSarthi AI','QuoteSaarthi') if reply else reply

    def handle_query(self, query, options=None):
        if self._looks_like_quote_request(query.lower()) and len(re.findall(r'\d+\s*(?:units?|pieces?|pcs?)\b',query,re.I))>1:
            return 'Abhi ek draft mein ek product supported hai. Har product ka naam, quantity aur GST rate alag bhejein.'
        if query.strip().lower() in {'cancel','cancel quote','new conversation','reset chat'}:
            from .agent import ConversationState
            self.state=ConversationState()
            self.pending_quote_query=None
            return 'Conversation reset. Product naam, quantity aur GST rate ke saath naya quotation pooch sakte hain.'
        if re.search(r'\bsecond[- ]best\b',query,re.I):
            offers=self.state.last_vendor_offers
            if not offers or len(offers[0].get('offers',[]))<2:
                return 'Selected product ka second vendor offer available nahi hai. Pehle product ki vendor listing search karein.'
            block=copy(offers[0]);block['offers']=block['offers'][1:2];block['vendor_count']=1
            return 'Second vendor option (catalogue price):\n'+self._format_bd_listing(query,[block])
        if query.strip().lower() in {'mujhe best product batao','best product','best vendor','mujhe best vendor batao'}:
            return 'Kaunsa product ya category chahiye? Product naam aur quantity batayein, phir catalogue ke vendor options compare karunga.'
        pending=getattr(self,'pending_quote_query',None)
        if pending and re.search(r'\b(?:gst|units?|qty|quantity|discount)\b',query,re.I) and not self._looks_like_quote_request(query.lower()):
            query=pending+' '+query
        if self._looks_like_quote_request(query.lower()) and not self.state.pending_invoice_flow:
            self.state.invoice_preferences.pop('gst_rate_percent',None)
        try:
            result=super().handle_query(query,options)
            self.pending_quote_query=None
            return result
        except ValueError:
            if self._looks_like_quote_request(query.lower()):
                self.pending_quote_query=query
            raise


@dataclass
class Conversation:
    agent: QuoteSaarthiAgent
    last_used: float = field(default_factory=monotonic)
    lock: RLock = field(default_factory=RLock)


class QuoteSaarthiService:
    def __init__(self, catalog, directory, ttl=7200, max_sessions=64):
        self.catalog=Path(catalog)
        self.directory=Path(directory)
        self.ttl=ttl
        self.max_sessions=max_sessions
        self.lock=RLock()
        self.sessions={}
        self.rag=None

    def conversation(self, token=None):
        with self.lock:
            now=monotonic()
            self.sessions={key:value for key,value in self.sessions.items() if now-value.last_used<self.ttl}
            if token:
                conversation=self.sessions.get(token)
                if not conversation:
                    raise LookupError('Conversation expired. Start a new QuoteSaarthi conversation.')
            else:
                if len(self.sessions)>=self.max_sessions:
                    raise RuntimeError('QuoteSaarthi is busy. Please try again shortly.')
                if not self.catalog.is_file():
                    raise FileNotFoundError('QuoteSaarthi catalogue is not configured. Prepare the handover catalogue on this server.')
                if self.rag is None:
                    self.rag=HospKartRAG(catalog_csv_path=self.catalog,lightweight_mode=True)
                    if self.rag.products_df is None or self.rag.products_df.empty:
                        self.rag=None
                        raise ValueError('Catalogue has no usable product rows.')
                token=secrets.token_urlsafe(32)
                directory=self.directory/'conversations'/token
                conversation=Conversation(QuoteSaarthiAgent(rag=self.rag,logs_dir=directory/'logs',exports_dir=directory/'exports'))
                self.sessions[token]=conversation
            conversation.last_used=now
            return token,conversation

    def chat(self, query, token=None, options=None):
        token,conversation=self.conversation(token)
        with conversation.lock:
            before=set(conversation.agent.exports_dir.iterdir())
            try:
                reply=conversation.agent.handle_query(query,options)
            except ValueError as error:
                # Clarification is a normal conversation outcome, not a crash.
                reply=str(error)
            exports=[]
            for path in sorted(set(conversation.agent.exports_dir.iterdir())-before):
                if path.suffix in {'.json','.pdf'}:
                    exports.append({'name':path.name,'format':path.suffix[1:]})
                    reply=reply.replace(str(path),path.name)
            return {'ok':True,'reply':reply,'response':reply,'session_id':token,'exports':exports,'assistant':'QuoteSaarthi'}

    def download(self, token, filename):
        if not token or not re.fullmatch(r'HOSP-[0-9_]+\.(?:json|pdf)',filename):
            raise LookupError('Export not found.')
        _,conversation=self.conversation(token)
        target=conversation.agent.exports_dir/filename
        if not target.is_file():
            raise LookupError('Export not found.')
        return target


_services={}
_services_lock=RLock()


def get_service(data_dir):
    directory=Path(data_dir)/'quotesaarthi'
    catalog=Path(os.getenv('QUOTESAARTHI_CATALOG_PATH',str(directory/'products.csv'))).expanduser().resolve()
    key=(str(catalog),str(directory.resolve()))
    with _services_lock:
        if key not in _services:
            _services[key]=QuoteSaarthiService(catalog,directory)
        return _services[key]
