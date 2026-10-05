"""ElectroPOS - electronics retail POS with barcode inventory and sales.
Runs on Windows/Linux/macOS (Python + Kivy) and builds to Android APK / Windows EXE.
"""
import os
import sqlite3
from functools import partial

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior

import db

NL = chr(10)  # newline character

try:
    from kivy_garden.zbarcam import ZBarCam  # optional camera scanning
    HAS_ZBAR = True
except Exception:
    try:
        from garden.zbarcam import ZBarCam
        HAS_ZBAR = True
    except Exception:
        ZBarCam = None
        HAS_ZBAR = False


# ---------------------------------------------------------------- UI helpers
def info_popup(title, text, dismiss_cb=None, height=0.5):
    box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
    box.add_widget(Label(text=text))
    ok = Button(text='OK', size_hint_y=None, height=dp(46),
                background_normal='', background_color=(0.2, 0.35, 0.6, 1))
    box.add_widget(ok)
    p = Popup(title=title, content=box, size_hint=(0.85, height), auto_dismiss=False)
    if dismiss_cb:
        p.bind(on_dismiss=dismiss_cb)
    ok.bind(on_release=p.dismiss)
    p.open()
    return p


# ---------------------------------------------------------------- KV
KV_MAIN = """
#:import dp kivy.metrics.dp

<Screen>:
    canvas.before:
        Color:
            rgba: 0.08, 0.08, 0.10, 1
        Rectangle:
            pos: self.pos
            size: self.size

<HeaderLabel@Label>:
    bold: True
    color: 0.55, 0.80, 1.0, 1
    text_size: self.size
    halign: 'left'
    valign: 'middle'
    shorten: True

<RowLabel@Label>:
    text_size: self.size
    halign: 'left'
    valign: 'middle'
    shorten: True
    color: 0.88, 0.88, 0.90, 1

<TopBar@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(52)
    padding: dp(4)
    spacing: dp(6)

<NavBtn@Button>:
    size_hint_x: None
    width: dp(110)
    background_normal: ''
    background_color: 0.22, 0.24, 0.28, 1
    color: 0.92, 0.92, 0.94, 1

<SmallBtn@Button>:
    background_normal: ''
    background_color: 0.30, 0.32, 0.37, 1
    color: 0.92, 0.92, 0.94, 1

<PrimaryBtn@Button>:
    background_normal: ''
    background_color: 0.10, 0.55, 0.32, 1
    color: 1, 1, 1, 1
    bold: True

<DangerBtn@Button>:
    background_normal: ''
    background_color: 0.68, 0.20, 0.20, 1
    color: 1, 1, 1, 1

<FieldLabel@Label>:
    size_hint_y: None
    height: dp(24)
    text_size: self.size
    halign: 'left'
    valign: 'middle'
    color: 0.75, 0.78, 0.85, 1

<FormInput@TextInput>:
    size_hint_y: None
    height: dp(44)
    multiline: False

<ProductRow>:
    orientation: 'horizontal'
    spacing: dp(4)
    RowLabel:
        text: root.name
        size_hint_x: 0.28
    RowLabel:
        text: root.barcode
        size_hint_x: 0.20
    RowLabel:
        text: root.category
        size_hint_x: 0.16
    RowLabel:
        text: root.price
        size_hint_x: 0.12
    RowLabel:
        text: root.stock
        size_hint_x: 0.08
    BoxLayout:
        size_hint_x: 0.16
        spacing: dp(4)
        SmallBtn:
            text: 'Edit'
            on_release: app.open_product_form(root.product_id)
        DangerBtn:
            text: 'Del'
            on_release: app.confirm_delete_product(root.product_id, root.name)

<SaleRow>:
    orientation: 'horizontal'
    spacing: dp(4)
    RowLabel:
        text: root.created
        size_hint_x: 0.36
    RowLabel:
        text: root.count
        size_hint_x: 0.20
    RowLabel:
        text: root.total
        size_hint_x: 0.24
    SmallBtn:
        text: 'View'
        size_hint_x: 0.20
        on_release: app.show_sale_detail(root.sale_id)

<POSScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(6)
        spacing: dp(6)
        TopBar:
            Label:
                text: 'ElectroPOS'
                font_size: '20sp'
                bold: True
                text_size: self.size
                halign: 'left'
                valign: 'middle'
            NavBtn:
                text: 'Inventory'
                on_release: root.manager.current = 'inventory'
            NavBtn:
                text: 'Sales'
                on_release: root.manager.current = 'sales'
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            spacing: dp(6)
            TextInput:
                id: barcode_input
                hint_text: 'Scan or type a barcode, then press Enter'
                multiline: False
                font_size: '17sp'
                on_text_validate: root.on_barcode_enter()
            NavBtn:
                id: scan_btn
                text: 'Scan'
                width: dp(80)
                on_release: root.manager.current = 'scan'
        GridLayout:
            cols: 5
            size_hint_y: None
            height: dp(26)
            spacing: dp(4)
            HeaderLabel:
                text: 'Item'
                size_hint_x: 0.38
            HeaderLabel:
                text: 'Price'
                size_hint_x: 0.18
            HeaderLabel:
                text: 'Qty'
                size_hint_x: 0.20
            HeaderLabel:
                text: 'Total'
                size_hint_x: 0.18
            HeaderLabel:
                text: ''
                size_hint_x: 0.06
        ScrollView:
            do_scroll_x: False
            GridLayout:
                id: cart_list
                cols: 1
                spacing: dp(2)
                size_hint_y: None
                height: self.minimum_height
        BoxLayout:
            size_hint_y: None
            height: dp(30)
            Label:
                id: items_label
                text: 'Items: 0'
            Label:
                id: total_label
                text: 'Total: $0.00'
                bold: True
                font_size: '18sp'
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(6)
            DangerBtn:
                text: 'Clear'
                on_release: root.clear_cart()
            PrimaryBtn:
                text: 'CHECKOUT'
                font_size: '18sp'
                on_release: root.checkout()

<InventoryScreen>:
    on_pre_enter: root.refresh()
    BoxLayout:
        orientation: 'vertical'
        padding: dp(6)
        spacing: dp(6)
        TopBar:
            NavBtn:
                text: '< POS'
                on_release: root.manager.current = 'pos'
            Label:
                text: 'Inventory'
                font_size: '20sp'
                bold: True
                text_size: self.size
                halign: 'left'
                valign: 'middle'
            NavBtn:
                text: '+ Add'
                on_release: app.open_product_form()
        TextInput:
            id: search
            hint_text: 'Search by name, barcode or category'
            multiline: False
            size_hint_y: None
            height: dp(42)
            on_text: root.refresh()
        GridLayout:
            cols: 6
            size_hint_y: None
            height: dp(26)
            spacing: dp(4)
            HeaderLabel:
                text: 'Name'
                size_hint_x: 0.28
            HeaderLabel:
                text: 'Barcode'
                size_hint_x: 0.20
            HeaderLabel:
                text: 'Category'
                size_hint_x: 0.16
            HeaderLabel:
                text: 'Price'
                size_hint_x: 0.12
            HeaderLabel:
                text: 'Stock'
                size_hint_x: 0.08
            HeaderLabel:
                text: ''
                size_hint_x: 0.16
        RecycleView:
            id: rv
            viewclass: 'ProductRow'
            do_scroll_x: False
            RecycleBoxLayout:
                default_size: None, dp(44)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(2)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            SmallBtn:
                text: 'Export CSV'
                on_release: root.export_csv()
            Label:
                id: inv_count
                text: ''
                text_size: self.size
                halign: 'right'
                valign: 'middle'

<ProductFormScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(4)
        TopBar:
            NavBtn:
                text: '< Back'
                on_release: root.manager.current = 'inventory'
            Label:
                text: 'Product'
                font_size: '20sp'
                bold: True
                text_size: self.size
                halign: 'left'
                valign: 'middle'
            NavBtn:
                text: 'Save'
                on_release: root.save()
        ScrollView:
            do_scroll_x: False
            GridLayout:
                cols: 1
                spacing: dp(4)
                size_hint_y: None
                height: self.minimum_height
                FieldLabel:
                    text: 'Barcode *'
                FormInput:
                    id: f_barcode
                FieldLabel:
                    text: 'Product name *'
                FormInput:
                    id: f_name
                FieldLabel:
                    text: 'Category'
                FormInput:
                    id: f_category
                FieldLabel:
                    text: 'Cost (buy price)'
                FormInput:
                    id: f_cost
                    input_filter: 'float'
                FieldLabel:
                    text: 'Sell price *'
                FormInput:
                    id: f_price
                    input_filter: 'float'
                FieldLabel:
                    text: 'Stock quantity'
                FormInput:
                    id: f_stock
                    input_filter: 'int'
                Widget:
                    size_hint_y: None
                    height: dp(12)
                PrimaryBtn:
                    text: 'SAVE PRODUCT'
                    size_hint_y: None
                    height: dp(50)
                    on_release: root.save()

<SalesScreen>:
    on_pre_enter: root.refresh()
    BoxLayout:
        orientation: 'vertical'
        padding: dp(6)
        spacing: dp(6)
        TopBar:
            NavBtn:
                text: '< POS'
                on_release: root.manager.current = 'pos'
            Label:
                text: 'Sales history'
                font_size: '20sp'
                bold: True
                text_size: self.size
                halign: 'left'
                valign: 'middle'
            Widget:
                size_hint_x: None
                width: dp(110)
        GridLayout:
            cols: 4
            size_hint_y: None
            height: dp(26)
            spacing: dp(4)
            HeaderLabel:
                text: 'Date'
                size_hint_x: 0.36
            HeaderLabel:
                text: 'Items'
                size_hint_x: 0.20
            HeaderLabel:
                text: 'Total'
                size_hint_x: 0.24
            HeaderLabel:
                text: ''
                size_hint_x: 0.20
        RecycleView:
            id: rv
            viewclass: 'SaleRow'
            do_scroll_x: False
            RecycleBoxLayout:
                default_size: None, dp(44)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(2)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            SmallBtn:
                text: 'Export CSV'
                on_release: root.export_csv()
            Label:
                id: sales_total
                text: ''
                text_size: self.size
                halign: 'right'
                valign: 'middle'
"""

SCAN_KV = """
<ScanScreen>:
    on_pre_enter: root.start()
    BoxLayout:
        orientation: 'vertical'
        ZBarCam:
            id: zbarcam
        NavBtn:
            text: 'Cancel'
            size_hint_x: 1
            size_hint_y: None
            height: dp(50)
            on_release: root.manager.current = 'pos'
"""


# ---------------------------------------------------------------- widgets
class ProductRow(RecycleDataViewBehavior, BoxLayout):
    product_id = NumericProperty(0)
    name = StringProperty('')
    barcode = StringProperty('')
    category = StringProperty('')
    price = StringProperty('')
    stock = StringProperty('')


class SaleRow(RecycleDataViewBehavior, BoxLayout):
    sale_id = NumericProperty(0)
    created = StringProperty('')
    count = StringProperty('')
    total = StringProperty('')


# ---------------------------------------------------------------- screens
class POSScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.cart = []

    def on_pre_enter(self):
        has_scan = self.manager.has_screen('scan')
        btn = self.ids.scan_btn
        btn.disabled = not has_scan
        btn.opacity = 1 if has_scan else 0
        btn.width = dp(80) if has_scan else 0
        self._refocus_soon()

    def _refocus_soon(self, *a):
        Clock.schedule_once(
            lambda dt: setattr(self.ids.barcode_input, 'focus', True), 0.2)

    # ---- barcode handling ----
    def on_barcode_enter(self):
        text = self.ids.barcode_input.text.strip()
        self.ids.barcode_input.text = ''
        self._refocus_soon()
        if not text:
            return
        p = db.get_product_by_barcode(text)
        if p is None:
            self._not_found(text)
            return
        if p['stock'] <= 0:
            info_popup('Out of stock', '"' + p['name'] + '" is out of stock.',
                       dismiss_cb=self._refocus_soon)
            return
        self.add_to_cart(dict(p))

    def _not_found(self, barcode):
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        box.add_widget(Label(text='Barcode not found:' + NL + barcode))
        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        yes = Button(text='Add as new product',
                     background_normal='', background_color=(0.1, 0.55, 0.32, 1))
        no = Button(text='Cancel')
        btns.add_widget(yes)
        btns.add_widget(no)
        box.add_widget(btns)
        p = Popup(title='Unknown barcode', content=box, size_hint=(0.8, 0.4),
                  auto_dismiss=False)
        yes.bind(on_release=lambda *_: (p.dismiss(),
                                         App.get_running_app().open_product_form(barcode=barcode)))
        no.bind(on_release=p.dismiss)
        p.open()

    # ---- cart ----
    def add_to_cart(self, p):
        for it in self.cart:
            if it['product_id'] == p['id']:
                if it['qty'] + 1 > p['stock']:
                    info_popup('Stock limit',
                               'Only ' + str(p['stock']) + ' x ' + p['name'] + ' in stock.',
                               dismiss_cb=self._refocus_soon)
                    return
                it['qty'] += 1
                self.refresh_cart()
                return
        self.cart.append({'product_id': p['id'], 'barcode': p['barcode'],
                          'name': p['name'], 'price': p['price'], 'qty': 1})
        self.refresh_cart()

    def refresh_cart(self):
        cl = self.ids.cart_list
        cl.clear_widgets()
        for i in range(len(self.cart)):
            cl.add_widget(self._cart_row(i))
        n = sum(it['qty'] for it in self.cart)
        total = sum(it['price'] * it['qty'] for it in self.cart)
        self.ids.items_label.text = 'Items: ' + str(n)
        self.ids.total_label.text = 'Total: $%.2f' % total

    def _cart_row(self, idx):
        it = self.cart[idx]
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        name = Label(text=it['name'], size_hint_x=0.38, shorten=True,
                     color=(0.9, 0.9, 0.92, 1))
        name.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        row.add_widget(name)
        row.add_widget(Label(text='$%.2f' % it['price'], size_hint_x=0.18,
                             color=(0.9, 0.9, 0.92, 1)))
        qty_box = BoxLayout(size_hint_x=0.20, spacing=dp(2))
        minus = Button(text='-')
        plus = Button(text='+')
        qlab = Label(text=str(it['qty']), color=(0.9, 0.9, 0.92, 1))
        minus.bind(on_release=partial(self.change_qty, idx, -1))
        plus.bind(on_release=partial(self.change_qty, idx, 1))
        qty_box.add_widget(minus)
        qty_box.add_widget(qlab)
        qty_box.add_widget(plus)
        row.add_widget(qty_box)
        row.add_widget(Label(text='$%.2f' % (it['price'] * it['qty']),
                             size_hint_x=0.18, color=(0.9, 0.9, 0.92, 1)))
        rm = Button(text='X', size_hint_x=0.06, background_normal='',
                    background_color=(0.68, 0.2, 0.2, 1), color=(1, 1, 1, 1))
        rm.bind(on_release=partial(self.remove_item, idx))
        row.add_widget(rm)
        return row

    def change_qty(self, idx, delta, *args):
        if not (0 <= idx < len(self.cart)):
            return
        it = self.cart[idx]
        if delta > 0:
            p = db.get_product(it['product_id'])
            if p and it['qty'] + 1 > p['stock']:
                info_popup('Stock limit',
                           'Only ' + str(p['stock']) + ' x ' + it['name'] + ' in stock.',
                           dismiss_cb=self._refocus_soon)
                return
        it['qty'] += delta
        if it['qty'] <= 0:
            self.cart.pop(idx)
        self.refresh_cart()

    def remove_item(self, idx, *args):
        if 0 <= idx < len(self.cart):
            self.cart.pop(idx)
            self.refresh_cart()

    def clear_cart(self):
        self.cart = []
        self.refresh_cart()
        self._refocus_soon()

    # ---- checkout ----
    def checkout(self):
        if not self.cart:
            info_popup('Empty cart', 'Scan at least one item before checkout.',
                       dismiss_cb=self._refocus_soon)
            return
        problems = db.check_stock(self.cart)
        if problems:
            msg = NL.join('%s: only %d left' % (name, avail)
                          for name, avail in problems)
            info_popup('Not enough stock', msg, dismiss_cb=self._refocus_soon)
            return
        total = sum(it['price'] * it['qty'] for it in self.cart)
        lines = NL.join('%s  x%d  $%.2f' % (it['name'], it['qty'],
                                            it['price'] * it['qty'])
                        for it in self.cart)
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        box.add_widget(Label(text=lines + NL + NL + ('TOTAL: $%.2f' % total)))
        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        ok = Button(text='Confirm & Pay', background_normal='',
                    background_color=(0.1, 0.55, 0.32, 1))
        cancel = Button(text='Cancel')
        btns.add_widget(ok)
        btns.add_widget(cancel)
        box.add_widget(btns)
        p = Popup(title='Checkout', content=box, size_hint=(0.85, 0.6),
                  auto_dismiss=False)
        ok.bind(on_release=lambda *_: (p.dismiss(), self.do_sale()))
        cancel.bind(on_release=p.dismiss)
        p.open()

    def do_sale(self):
        try:
            sale_id, total = db.create_sale(self.cart)
        except sqlite3.Error as e:
            info_popup('Database error', str(e), dismiss_cb=self._refocus_soon)
            return
        self.cart = []
        self.refresh_cart()
        self._show_receipt(sale_id, total)

    def _show_receipt(self, sale_id, total):
        sale = db.get_sale(sale_id)
        items = db.get_sale_items(sale_id)
        lines = NL.join('%s  x%d  @ $%.2f' % (i['name'], i['qty'], i['price'])
                        for i in items)
        text = NL.join(('Sale #%d  %s' % (sale_id, sale['created_at']),
                        '-' * 28, lines, 'TOTAL: $%.2f' % total))
        info_popup('Sale complete', text, dismiss_cb=self._refocus_soon,
                   height=0.6)


class InventoryScreen(Screen):
    def refresh(self):
        term = self.ids.search.text.strip()
        rows = db.search_products(term)
        self.ids.rv.data = [
            {'product_id': r['id'], 'name': r['name'], 'barcode': r['barcode'],
             'category': r['category'] or '', 'price': '$%.2f' % r['price'],
             'stock': str(r['stock'])}
            for r in rows
        ]
        self.ids.inv_count.text = '%d products' % len(rows)

    def export_csv(self):
        rows = db.search_products('')
        path = db.export_csv('inventory.csv',
                             ['barcode', 'name', 'category', 'cost', 'price', 'stock'],
                             rows)
        info_popup('Exported', 'Saved to:' + NL + path)


class ProductFormScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.product_id = None

    def set_product(self, product_id=None, barcode=''):
        self.product_id = product_id
        ids = self.ids
        if product_id:
            p = db.get_product(product_id)
            ids.f_barcode.text = p['barcode']
            ids.f_name.text = p['name']
            ids.f_category.text = p['category'] or ''
            ids.f_cost.text = '%.2f' % p['cost']
            ids.f_price.text = '%.2f' % p['price']
            ids.f_stock.text = str(p['stock'])
        else:
            for w in (ids.f_barcode, ids.f_name, ids.f_category,
                      ids.f_cost, ids.f_price, ids.f_stock):
                w.text = ''
            ids.f_barcode.text = barcode

    def save(self):
        ids = self.ids
        barcode = ids.f_barcode.text.strip()
        name = ids.f_name.text.strip()
        if not barcode or not name:
            info_popup('Missing fields', 'Barcode and product name are required.')
            return
        try:
            price = float(ids.f_price.text) if ids.f_price.text.strip() else 0.0
            cost = float(ids.f_cost.text) if ids.f_cost.text.strip() else 0.0
            stock = int(float(ids.f_stock.text)) if ids.f_stock.text.strip() else 0
        except ValueError:
            info_popup('Invalid numbers', 'Check the cost / price / stock fields.')
            return
        try:
            if self.product_id:
                db.update_product(self.product_id, barcode, name,
                                  ids.f_category.text.strip(), cost, price, stock)
            else:
                db.add_product(barcode, name, ids.f_category.text.strip(),
                               cost, price, stock)
        except sqlite3.IntegrityError:
            info_popup('Duplicate barcode',
                       '"' + barcode + '" already exists. Edit that product instead.')
            return
        self.manager.current = 'inventory'
        self.manager.get_screen('inventory').refresh()


class SalesScreen(Screen):
    def refresh(self):
        rows = db.list_sales()
        self.ids.rv.data = [
            {'sale_id': r['id'], 'created': r['created_at'],
             'count': str(r['items']), 'total': '$%.2f' % r['total']}
            for r in rows
        ]
        self.ids.sales_total.text = '%d sales' % len(rows)

    def export_csv(self):
        rows = db.list_sales()
        path = db.export_csv('sales.csv', ['id', 'created_at', 'items', 'total'], rows)
        info_popup('Exported', 'Saved to:' + NL + path)


class ScanScreen(Screen):
    def start(self):
        self._done = False
        self.ids.zbarcam.bind(symbols=self.on_symbols)

    def on_symbols(self, instance, symbols):
        if self._done or not symbols:
            return
        self._done = True
        data = getattr(symbols[0], 'data', b'')
        if isinstance(data, bytes):
            data = data.decode('utf-8', 'ignore')
        Clock.schedule_once(lambda dt: self._finish(data), 0)

    def _finish(self, data):
        self.manager.current = 'pos'
        pos = self.manager.get_screen('pos')
        pos.ids.barcode_input.text = data
        pos.on_barcode_enter()


# ---------------------------------------------------------------- app
class ElectroPOSApp(App):
    def build(self):
        self.title = 'ElectroPOS'
        os.makedirs(self.user_data_dir, exist_ok=True)
        db.set_db_path(os.path.join(self.user_data_dir, 'electropos.db'))
        db.get_db()
        sm = ScreenManager()
        sm.add_widget(POSScreen(name='pos'))
        sm.add_widget(InventoryScreen(name='inventory'))
        sm.add_widget(ProductFormScreen(name='product_form'))
        sm.add_widget(SalesScreen(name='sales'))
        if HAS_ZBAR:
            sm.add_widget(ScanScreen(name='scan'))
        self.sm = sm
        return sm

    def open_product_form(self, product_id=None, barcode=''):
        form = self.sm.get_screen('product_form')
        form.set_product(product_id, barcode)
        self.sm.current = 'product_form'

    def confirm_delete_product(self, product_id, name):
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        box.add_widget(Label(text='Delete "' + name + '"?'))
        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        yes = Button(text='Delete', background_normal='',
                     background_color=(0.68, 0.2, 0.2, 1))
        no = Button(text='Cancel')
        btns.add_widget(yes)
        btns.add_widget(no)
        box.add_widget(btns)
        p = Popup(title='Confirm delete', content=box, size_hint=(0.7, 0.35),
                  auto_dismiss=False)

        def _do_delete(*_):
            db.delete_product(product_id)
            p.dismiss()
            self.sm.get_screen('inventory').refresh()

        yes.bind(on_release=_do_delete)
        no.bind(on_release=p.dismiss)
        p.open()

    def show_sale_detail(self, sale_id):
        sale = db.get_sale(sale_id)
        items = db.get_sale_items(sale_id)
        lines = NL.join('%s  x%d  @ $%.2f = $%.2f'
                        % (i['name'], i['qty'], i['price'], i['price'] * i['qty'])
                        for i in items)
        text = NL.join(('Sale #%d  %s' % (sale_id, sale['created_at']),
                        '-' * 28, lines, 'TOTAL: $%.2f' % sale['total']))
        info_popup('Sale detail', text, height=0.6)


KV = KV_MAIN + (SCAN_KV if HAS_ZBAR else '')
Builder.load_string(KV)


if __name__ == '__main__':
    ElectroPOSApp().run()
