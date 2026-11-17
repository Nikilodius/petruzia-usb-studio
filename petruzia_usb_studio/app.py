import json
import math
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from serial.tools import list_ports
from google.protobuf.json_format import MessageToDict
import behaviors_pb2 as behaviors
import keymap_pb2 as keymap
from protocol import StudioClient, RpcError, LockedError

# Style: chat.eblo.id (Chatterino+) — near-black, thin panels, soft purple accent
BG='#0a0a0d'; PANEL='#0e0e11'; PANEL_2='#131318'; PANEL_3='#101014'; LINE='#22222b'
ACC='#b8a7f0'; BLUE='#4a9eff'; GREEN='#57d9a3'; AMBER='#ffd54a'; RED='#ff6b7a'
TEXT='#e8e8ee'; MUTED='#6c6c78'; DIM='#4a4a56'
KEY_FILL='#16161d'; KEY_FILL_HOVER='#1e1e26'; KEY_FILL_SEL='#232330'

KEYS = {chr(65+i): 0x70004+i for i in range(26)}
KEYS.update({str(i): 0x7001d+i for i in range(1,10)})
KEYS.update({'0':0x70027,'Enter':0x70028,'Esc':0x70029,'Backspace':0x7002a,'Tab':0x7002b,'Space':0x7002c,'Minus':0x7002d,'Equal':0x7002e,'[':0x7002f,']':0x70030,'Backslash':0x70031,'Semicolon':0x70033,'Quote':0x70034,'Grave':0x70035,'Comma':0x70036,'Dot':0x70037,'Slash':0x70038,'CapsLock':0x70039,'Right':0x7004f,'Left':0x70050,'Down':0x70051,'Up':0x70052,'Delete':0x7004c})
KEYS.update({f'F{i}':0x70039+i for i in range(1,13)})
KEYS.update({name:0x700e0+i for i,name in enumerate(['LCTRL','LSHIFT','LALT','LGUI','RCTRL','RSHIFT','RALT','RGUI'])})
KEY_NAMES = {v:k for k,v in KEYS.items()}

RU_KEY = {'LCTRL':'Ctrl','LSHIFT':'Shift','LALT':'Alt','LGUI':'Win','RCTRL':'Ctrl','RSHIFT':'Shift','RALT':'Alt','RGUI':'Win','BACKSPACE':'Backspace','CAPSLOCK':'CapsLock','DELETE':'Delete','SEMICOLON':';','QUOTE':"'",'MINUS':'-','EQUAL':'=','COMMA':',','DOT':'.','SLASH':'/','GRAVE':'`','LEFT':'←','RIGHT':'→','UP':'↑','DOWN':'↓','ENTER':'Enter','SPACE':'Пробел','TAB':'Tab','ESC':'Esc'}

PALETTE_GROUPS = [
    ('Буквы', list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
    ('Цифры', list('0123456789')),
    ('Клавиши F', [f'F{i}' for i in range(1,13)]),
    ('Стрелки', ['Left','Up','Down','Right']),
    ('Модификаторы', ['LCTRL','LSHIFT','LALT','LGUI']),
    ('Основные', ['Space','Enter','Tab','Esc','Backspace','Delete','CapsLock']),
    ('Знаки', ['Comma','Dot','Slash','Semicolon','Quote','Minus','Equal','Grave','[',']','Backslash']),
]

def palette_name(k):
    return RU_KEY.get(k.upper(), RU_KEY.get(k, k))

def blend(c1,c2,k):
    a=[int(c1[i:i+2],16) for i in (1,3,5)]; b=[int(c2[i:i+2],16) for i in (1,3,5)]
    m=[round(x+(y-x)*k) for x,y in zip(a,b)]
    return '#%02x%02x%02x'%tuple(m)


class VirusCube(tk.Canvas):
    """Псевдо-3D вращающийся «вирус-куб»: каркасный куб с пульсирующими шипами."""
    CUBE = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    EDGES = []
    for _i, _a in enumerate(CUBE):
        for _j, _b in enumerate(CUBE):
            if _j > _i and sum(p != q for p, q in zip(_a, _b)) == 1:
                EDGES.append((_i, _j))
    FACES = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    PALETTE = {
        'offline': ('#241a20', RED,    '#1a151a'),
        'locked':  ('#2b2416', AMBER,  '#201c10'),
        'live':    ('#161c26', BLUE,   '#1e1830'),
        'ready':   ('#15221d', GREEN,  '#171e1c'),
    }

    def __init__(self, master, size=110, **kw):
        super().__init__(master, width=size, height=size, bg=BG, highlightthickness=0, **kw)
        self.size=size; self.state='offline'; self.t=0.0
        self._tick()

    def set_state(self, state):
        if state in self.PALETTE: self.state=state

    def _tick(self):
        if not self.winfo_exists(): return
        try:
            if self.winfo_viewable():
                self.t+=0.085; self._draw()
        except tk.TclError:
            return
        self.after(95,self._tick)

    def _rot(self,v):
        ax,ay=self.t*0.9,self.t*1.35
        x,y,z=v
        y,z=y*math.cos(ax)-z*math.sin(ax), y*math.sin(ax)+z*math.cos(ax)
        x,z=x*math.cos(ay)+z*math.sin(ay), -x*math.sin(ay)+z*math.cos(ay)
        return x,y,z

    def _proj(self,v):
        fov=3.4; k=fov/(fov+v[2]*0.9)
        c=self.size/2
        return c+v[0]*k*c*0.42, c+v[1]*k*c*0.42, v[2]

    def _len(self,v):
        s=self.size/2
        p=self._proj(v)
        return p[0]+(v[0]*0.32)*s*p[2]*0.35, p[1]+(v[1]*0.32)*s*p[2]*0.35

    def _draw(self):
        self.delete('all')
        dark,main,glow=self.PALETTE[self.state]
        pulse=1.0+0.25*math.sin(self.t*2.4)
        verts=[self._rot(v) for v in self.CUBE]
        pts=[self._proj(v) for v in verts]
        order=sorted(range(len(self.EDGES)),key=lambda e:(pts[self.EDGES[e][0]][2]+pts[self.EDGES[e][1]][2]))
        for e in order:
            a,b=pts[self.EDGES[e][0]],pts[self.EDGES[e][1]]
            depth=(a[2]+b[2])/2
            shade=max(0.25,min(1.0,0.5-depth*0.35))
            width=2 if depth>0 else 1
            self.create_line(a[0],a[1],b[0],b[1],fill=blend(dark,main,shade),width=width)
        for i,(v,p) in enumerate(zip(verts,pts)):
            tip=self._len([c*pulse*0.75 for c in v])
            self.create_line(p[0],p[1],tip[0],tip[1],fill=blend(dark,main,0.75),width=1)
            r=2.2+0.8*math.sin(self.t*3+i)
            self.create_oval(tip[0]-r,tip[1]-r,tip[0]+r,tip[1]+r,fill=main,outline='')
        for f in self.FACES:
            v=self._rot(f); tip=self._len([c*pulse*0.62 for c in v])
            self.create_line(0,0,tip[0],tip[1],fill=glow,width=1)
        c=self.size/2
        self.create_oval(c-11,c-11,c+11,c+11,fill=dark,outline=glow,width=2)
        self.create_oval(c-4,c-4,c+4,c+4,fill=main,outline='')


class AmbientHeader(tk.Canvas):
    """Шапка в стиле chat.eblo.id: радиальное свечение, лёгкие орбы, мягкое мерцание заголовка."""
    TITLE_PALETTE=[TEXT,'#cfc4f7',ACC,'#8f7ff0']

    def __init__(self, master, badge_label, height=118, **kw):
        super().__init__(master,width=640,height=height,bg=BG,highlightthickness=0,**kw)
        self.height=height; self.t=0.0
        self.badge=badge_label
        self.badge_window=self.create_window(22,18,window=self.badge,anchor='nw')
        self.title_id=self.create_text(24,50,text='PETRUZIA  STUDIO',anchor='w',font=('Segoe UI',25,'bold'))
        self.sub_id=self.create_text(26,84,text='настройка раскладки в реальном времени — без перепрошивки',anchor='w',font=('Segoe UI',10),fill=MUTED)
        self.orbs=[{'x':0.72,'y':0.42,'r':150,'c':ACC,'sp':0.16,'ph':0.0,'max':0.13},
                   {'x':0.30,'y':0.85,'r':110,'c':BLUE,'sp':0.11,'ph':2.1,'max':0.09}]
        self._tick()

    def _tick(self):
        if not self.winfo_exists(): return
        try:
            if not self.winfo_viewable():
                self.after(200,self._tick); return
            self.t+=0.09
            w=max(self.winfo_width(),640); h=self.height
            self.delete('orbs')
            # radial stage glow like the site
            gx,gy=0.72*w,0.42*h
            rings=9; R=w*0.8
            for i in range(rings,0,-1):
                k=0.05*(1-i/rings)
                self.create_oval(gx-R*i/rings,gy-R*i/rings*0.8,gx+R*i/rings,gy+R*i/rings*0.8,fill=blend(BG,'#181622',k),outline='',tags='orbs')
            for o in self.orbs:
                cx=(o['x']+0.06*math.sin(self.t*o['sp']+o['ph']))*w
                cy=(o['y']+0.08*math.cos(self.t*o['sp']*0.8+o['ph']))*h
                r=o['r']*(1.0+0.10*math.sin(self.t*0.6+o['ph']))
                for i in range(6,0,-1):
                    k=o['max']*(1-i/6)**2
                    self.create_oval(cx-r*i/6,cy-r*i/6,cx+r*i/6,cy+r*i/6,fill=blend(BG,o['c'],k),outline='',tags='orbs')
            self.tag_lower('orbs')
            pal=self.TITLE_PALETTE
            k=self.t*0.30; i0=int(k)%len(pal); i1=(i0+1)%len(pal); frac=k-int(k)
            self.itemconfig(self.title_id,fill=blend(pal[i0],pal[i1],frac))
            self.itemconfig(self.badge_window,width=250)
            pulse=0.5+0.5*math.sin(self.t*1.4)
            self.badge.config(bg=blend(PANEL_2,'#191922',0.3+0.3*pulse))
        except tk.TclError:
            return
        self.after(140,self._tick)


class Card(tk.Frame):
    """Карточка статуса: цветная полоса, заголовок, значение."""
    def __init__(self, master, title, accent):
        super().__init__(master, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        self.accent=accent
        bar=tk.Frame(self,bg=accent,width=3); bar.pack(side='left',fill='y')
        inner=tk.Frame(self,bg=PANEL); inner.pack(side='left',fill='both',expand=True,padx=14,pady=10)
        self.title_label=tk.Label(inner,text=title,bg=PANEL,fg=MUTED,font=('Segoe UI',8,'bold'),anchor='w'); self.title_label.pack(fill='x')
        self.value_label=tk.Label(inner,text='—',bg=PANEL,fg=accent,font=('Segoe UI',13,'bold'),anchor='w'); self.value_label.pack(fill='x',pady=(2,0))
        self.sub_label=tk.Label(inner,text='',bg=PANEL,fg=DIM,font=('Segoe UI',8),anchor='w'); self.sub_label.pack(fill='x')
    def set(self, value, sub='', color=None, flash=False):
        c=color or self.accent
        self.value_label.config(text=value, fg=c)
        self.sub_label.config(text=sub)
        if flash: self._flash(c)
    def _flash(self,c):
        steps=8
        def step(i):
            try:
                if i>=steps:
                    self.value_label.config(bg=PANEL); self.title_label.config(bg=PANEL); self.sub_label.config(bg=PANEL); return
                k=abs(1-2*i/steps)
                bg=blend(PANEL,'#1e1c2b',0.7*k)
                self.value_label.config(bg=bg); self.title_label.config(bg=bg); self.sub_label.config(bg=bg)
                self.after(60,lambda: step(i+1))
            except tk.TclError: pass
        step(0)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Petruzia Studio — настройка раскладки')
        self.geometry('1220x850'); self.minsize(1000,700); self.configure(bg=BG)
        for base in (getattr(sys,'_MEIPASS',None), os.path.dirname(os.path.abspath(__file__))):
            if base:
                ico=os.path.join(base,'icon.ico')
                if os.path.exists(ico):
                    try: self.iconbitmap(ico)
                    except tk.TclError: pass
                    break
        self.client=None; self.km=None; self.physical=None; self.behaviors={}; self.locked=True; self.busy=False
        self.results=queue.Queue(); self.session=0; self.device_name='—'
        self.selected=None; self.key_canvas=None; self.canvas_map={}
        self.protocol('WM_DELETE_WINDOW', self.close)
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('TButton', padding=(13,8), background=PANEL_2, foreground=TEXT, bordercolor=LINE, lightcolor=PANEL_2, darkcolor=PANEL_2, font=('Segoe UI',9,'bold'))
        style.map('TButton', background=[('active', '#1b1b24'), ('disabled', '#101014')], foreground=[('disabled', DIM)])
        style.configure('Primary.TButton', padding=(16,8), background=ACC, foreground='#16131f', bordercolor=ACC, font=('Segoe UI',9,'bold'))
        style.map('Primary.TButton', background=[('active', '#cec3fb'), ('disabled', '#232030')], foreground=[('disabled', '#575065')])
        style.configure('Save.TButton', padding=(16,8), background=GREEN, foreground='#0b1f16', bordercolor=GREEN, font=('Segoe UI',9,'bold'))
        style.map('Save.TButton', background=[('active', '#8ceac3'), ('disabled', '#17251f')], foreground=[('disabled', '#3f5c50')])
        style.configure('TCombobox', padding=6, fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=ACC)
        style.map('TCombobox', fieldbackground=[('readonly', PANEL_2)], foreground=[('readonly', TEXT)])
        for sname in ('Pal.Vertical.TScrollbar','Keys.Horizontal.TScrollbar'):
            style.configure(sname, troughcolor=PANEL_3, background='#23232e', bordercolor=LINE,
                            arrowcolor=MUTED, lightcolor='#23232e', darkcolor='#23232e', gripcount=0, arrowsize=12)
            style.map(sname, background=[('active','#3a3a4a'),('pressed','#46465a')])
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(20,9), background=PANEL_3, foreground=MUTED, borderwidth=0, font=('Segoe UI',10,'bold'))
        style.map('TNotebook.Tab', background=[('selected', PANEL_2)], foreground=[('selected', ACC)])
        self.build(); self.refresh_ports(); self.after(80,self.poll)

    def build(self):
        header=tk.Frame(self,bg=BG); header.pack(fill='x')
        self.badge=tk.Label(header,text='●  НЕ ПОДКЛЮЧЕНО',fg=MUTED,bg=PANEL_2,font=('Segoe UI',10,'bold'),padx=14,pady=7)
        self.ambient=AmbientHeader(header,self.badge); self.ambient.pack(side='left',fill='both',expand=True)
        self.cube=VirusCube(header,size=110); self.cube.pack(side='right',padx=(0,18),pady=5)

        cards=tk.Frame(self,bg=BG,padx=24); cards.pack(fill='x')
        self.card_conn=Card(cards,'ПОДКЛЮЧЕНИЕ',BLUE); self.card_conn.pack(side='left',padx=(0,10))
        self.card_dev=Card(cards,'КЛАВИАТУРА',ACC); self.card_dev.pack(side='left',padx=10)
        self.card_layers=Card(cards,'СЛОИ',AMBER); self.card_layers.pack(side='left',padx=10)
        self.card_changes=Card(cards,'НЕСОХРАНЁННЫЕ ПРАВКИ',RED); self.card_changes.pack(side='left',padx=10)
        self.card_conn.set('НЕТ','выбери порт ниже')
        self.card_dev.set('—','ожидание подключения')
        self.card_layers.set('—','нажми «Прочитать»')
        self.card_changes.set('—','нет данных')

        panel=tk.Frame(self,bg=PANEL,highlightbackground=LINE,highlightthickness=1); panel.pack(fill='x',padx=24,pady=(14,0))
        tk.Label(panel,text='USB-ПОРТ',fg=MUTED,bg=PANEL,font=('Segoe UI',8,'bold')).pack(side='left',padx=(12,8))
        self.port=ttk.Combobox(panel,width=38,state='readonly'); self.port.pack(side='left',padx=(0,8))
        ttk.Button(panel,text='Обновить',command=self.refresh_ports).pack(side='left',padx=3)
        self.connect_btn=ttk.Button(panel,text='Подключить',style='Primary.TButton',command=self.connect); self.connect_btn.pack(side='left',padx=3)
        self.read_btn=ttk.Button(panel,text='Прочитать клавиатуру',command=self.read_keyboard); self.read_btn.pack(side='left',padx=3)
        self.save_btn=ttk.Button(panel,text='Сохранить в память',style='Save.TButton',command=self.save); self.save_btn.pack(side='left',padx=3)
        self.discard_btn=ttk.Button(panel,text='Отменить правки',command=self.discard); self.discard_btn.pack(side='left',padx=3)
        self.backup_btn=ttk.Button(panel,text='Резервная копия',command=self.backup); self.backup_btn.pack(side='left',padx=3)

        self.hint=tk.Label(self,text='  Как пользоваться: Подключить → Прочитать клавиатуру → кликни клавишу, потом кликни новую в панели справа → Сохранить в память',fg=MUTED,bg=BG,anchor='w',font=('Segoe UI',9)); self.hint.pack(fill='x',pady=(8,0))

        body=tk.Frame(self,bg=BG,padx=24,pady=10); body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=BG); left.pack(side='left',fill='both',expand=True)
        self.layers=ttk.Notebook(left); self.layers.pack(fill='both',expand=True)

        self.editor=tk.Frame(body,bg=PANEL,highlightbackground=LINE,highlightthickness=1,width=340); self.editor.pack(side='right',fill='y',padx=(12,0)); self.editor.pack_propagate(False)
        self.build_editor()

        log_panel=tk.Frame(left,bg=PANEL_3,highlightbackground=LINE,highlightthickness=1); log_panel.pack(fill='x',pady=(10,0))
        tk.Label(log_panel,text='СОБЫТИЯ',bg=PANEL_3,fg=DIM,font=('Segoe UI',8,'bold')).pack(anchor='w',padx=12,pady=(7,0))
        self.log=tk.Text(log_panel,height=4,bg=PANEL_3,fg=MUTED,insertbackground=ACC,relief='flat',state='disabled',font=('Consolas',9),padx=12,pady=6); self.log.pack(fill='x')
        self.note('Нативное приложение. Официальный протокол ZMK Studio — без браузера и без перепрошивки.')
        self.update_controls()

    def build_editor(self):
        tk.Label(self.editor,text='ПЕРЕНАЗНАЧЕНИЕ КЛАВИШИ',fg=ACC,bg=PANEL,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=16,pady=(14,2))
        self.ed_sel=tk.Label(self.editor,text='Кликни по клавише слева',fg=MUTED,bg=PANEL,font=('Segoe UI',9),anchor='w'); self.ed_sel.pack(fill='x',padx=16)
        tk.Label(self.editor,text='СЕЙЧАС НАЗНАЧЕНО',fg=MUTED,bg=PANEL,font=('Segoe UI',8,'bold'),anchor='w').pack(fill='x',padx=16,pady=(12,2))
        self.ed_cur=tk.Label(self.editor,text='—',fg=TEXT,bg=PANEL_2,font=('Segoe UI',10,'bold'),anchor='w',padx=10,pady=8,justify='left'); self.ed_cur.pack(fill='x',padx=16)
        tk.Label(self.editor,text='КЛИКНИ НОВУЮ КЛАВИШУ — ПРИМЕНИТСЯ СРАЗУ',fg=MUTED,bg=PANEL,font=('Segoe UI',8,'bold'),anchor='w').pack(fill='x',padx=16,pady=(14,4))

        wrap=tk.Frame(self.editor,bg=PANEL); wrap.pack(fill='both',expand=True,padx=10)
        canvas=tk.Canvas(wrap,bg=PANEL,highlightthickness=0); sb=ttk.Scrollbar(wrap,orient='vertical',command=canvas.yview,style='Pal.Vertical.TScrollbar')
        grid=tk.Frame(canvas,bg=PANEL)
        grid.bind('<Configure>',lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0,0),window=grid,anchor='nw'); canvas.configure(yscrollcommand=sb.set,yscrollincrement=24)
        sb.pack(side='right',fill='y'); canvas.pack(side='left',fill='both',expand=True)
        def _on_wheel(e):
            canvas.yview_scroll(-3 if e.delta>0 else 3,'units')
        self._palette_wheel=_on_wheel
        canvas.bind('<MouseWheel>',_on_wheel)
        self.grid_frame=grid

        self.remap_buttons=[]
        for title,keys in PALETTE_GROUPS:
            lab=tk.Label(grid,text=title.upper(),fg=DIM,bg=PANEL,font=('Segoe UI',7,'bold'),anchor='w'); lab.pack(fill='x',padx=8,pady=(8,2)); lab.bind('<MouseWheel>',self._palette_wheel)
            holder=tk.Frame(grid,bg=PANEL); holder.pack(fill='x',padx=6); holder.bind('<MouseWheel>',self._palette_wheel)
            for idx,k in enumerate(keys):
                b=tk.Button(holder,text=palette_name(k),bg=PANEL_2,fg=TEXT,activebackground=ACC,activeforeground='#16131f',relief='flat',font=('Segoe UI',8,'bold'),pady=5,bd=0,
                            command=lambda n=k:self.remap(n))
                b.grid(row=idx//4,column=idx%4,padx=2,pady=2,sticky='nsew')
                b.bind('<Enter>',lambda e,w=b: w.config(bg=KEY_FILL_HOVER) if str(w['command'])!='' else None)
                b.bind('<Leave>',lambda e,w=b: w.config(bg=PANEL_2))
                b.bind('<MouseWheel>',self._palette_wheel)
                self.remap_buttons.append(b)
            for cidx in range(4): holder.columnconfigure(cidx,weight=1)

        self.ed_note=tk.Label(self.editor,text='',fg=GREEN,bg=PANEL,font=('Segoe UI',9,'bold'),anchor='w',justify='left',wraplength=300); self.ed_note.pack(fill='x',padx=16,pady=(8,10))

    def note(self,text):
        self.log.config(state='normal'); self.log.insert('end',text+'\n'); self.log.see('end'); self.log.config(state='disabled')
    def set_badge(self,text,fg):
        self.badge.config(text=text,fg=fg)
    def update_cards(self):
        connected=self.client is not None
        if connected:
            self.card_conn.set('USB · '+self.port.get().split(' — ')[0],'соединение установлено')
            self.card_dev.set(self.device_name,'прошивка ZMK Studio')
            if self.km is not None:
                self.card_layers.set(str(len(self.km.layers)),'кликни клавишу для правки')
            else:
                self.card_layers.set('—','нажми «Прочитать»')
            if self.km is None: self.card_changes.set('—','нет данных')
            elif self.locked: self.card_changes.set('ЗАКРЫТА','нажми разблокировку',AMBER)
            else: self.card_changes.set('ОТКРЫТА','можно редактировать',GREEN)
        else:
            self.card_conn.set('НЕТ','выбери порт ниже')
            self.card_dev.set('—','ожидание подключения')
            self.card_layers.set('—','нажми «Прочитать»')
            self.card_changes.set('—','нет данных')
    def update_controls(self):
        connected=self.client is not None
        for b in (self.read_btn,self.save_btn,self.discard_btn): b.config(state='normal' if connected and not self.busy else 'disabled')
        if self.locked or self.km is None:
            self.save_btn.config(state='disabled'); self.discard_btn.config(state='disabled')
        self.connect_btn.config(state='disabled' if self.busy else 'normal',text='Отключить' if connected else 'Подключить')
        self.update_cards()

    def task(self,job,done):
        if self.busy: return
        self.busy=True; self.update_controls(); session=self.session
        def work():
            try: self.results.put((session,done,job(),None))
            except Exception as exc: self.results.put((session,None,None,exc))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                session,done,value,error=self.results.get_nowait()
                if session!=self.session: continue
                self.busy=False
                if error: self.show_error(error)
                else: done(value)
                self.update_controls()
        except queue.Empty: pass
        if self.client:
            try:
                while True:
                    kind,event=self.client.events.get_nowait()
                    if kind=='disconnected':
                        self.set_badge('●  СОЕДИНЕНИЕ ПОТЕРЯНО',RED); self.note('USB отключён: '+str(event)); self.disconnect(); break
                    if event.WhichOneof('subsystem')=='core' and event.core.WhichOneof('notification_type')=='lock_state_changed':
                        self.locked=event.core.lock_state_changed!=1
                        self.note('Клавиатура: '+('ЗАКРЫТА' if self.locked else 'ОТКРЫТА для правок'))
                        if self.locked:
                            self.cube.set_state('locked'); self.set_badge('●  ЗАБЛОКИРОВАНА',AMBER)
                        else:
                            self.cube.set_state('ready'); self.set_badge('●  ГОТОВА К ПРАВКАМ',GREEN)
                        self.update_controls()
                    elif event.WhichOneof('subsystem')=='keymap': self.note('На клавиатуре есть несохранённые правки: '+str(event.keymap.unsaved_changes_status_changed))
            except queue.Empty: pass
        self.after(80,self.poll)

    def refresh_ports(self):
        ports=[f'{p.device} — {p.description}' for p in list_ports.comports()]
        self.port['values']=ports
        if ports: self.port.current(0)
        else: self.port.set('')
        self.note('Порты: '+('; '.join(ports) if ports else 'нет. Прошивка с ZMK Studio создаёт отдельный USB-порт.'))

    def connect(self):
        if self.client: self.disconnect(); self.set_badge('●  НЕ ПОДКЛЮЧЕНО',MUTED); self.note('Отключено. Изменения НЕ сохранялись автоматически.'); return
        if not self.port.get(): return messagebox.showwarning('Порт не выбран','Подключи клавиатуру по USB и нажми «Обновить».')
        device=self.port.get().split(' — ',1)[0]; self.session+=1
        def open_port():
            client=StudioClient(device)
            try:
                info=client.call('core','get_device_info'); state=client.call('core','get_lock_state'); return client,info,state
            except Exception:
                client.close(); raise
        def opened(data):
            self.client,info,state=data; self.locked=state!=1; self.device_name=info.name
            self.card_dev.set(self.device_name,'прошивка ZMK Studio',flash=True)
            self.cube.set_state('ready' if not self.locked else 'locked')
            self.set_badge('●  ЗАБЛОКИРОВАНА' if self.locked else '●  ГОТОВА К ПРАВКАМ',AMBER if self.locked else GREEN)
            self.note(f'Клавиатура найдена: {info.name} (серийный номер {info.serial_number.hex()})')
            if not self.locked: self.read_keyboard()
        self.set_badge('●  ПОДКЛЮЧЕНИЕ…',BLUE); self.task(open_port,opened)

    def disconnect(self):
        self.session+=1; self.busy=False
        if self.client: self.client.close()
        self.client=None; self.km=None; self.behaviors={}; self.physical=None; self.locked=True; self.device_name='—'
        self.cube.set_state('offline'); self.clear_editor()
        for tab in self.layers.tabs(): self.layers.forget(tab)
        self.update_controls()

    def read_keyboard(self):
        if not self.client: return
        client=self.client
        def read():
            lock=client.call('core','get_lock_state')
            if lock!=1: raise LockedError('Клавиатура закрыта для правок. Нажми на ней разблокировку (&studio_unlock) и нажми «Прочитать» снова.')
            km=client.call('keymap','get_keymap'); physical=client.call('keymap','get_physical_layouts')
            ids=client.call('behaviors','list_all_behaviors'); details={}
            for bid in ids.behaviors:
                details[bid]=client.call('behaviors','get_behavior_details',behaviors.GetBehaviorDetailsRequest(behavior_id=bid))
            unsaved=client.call('keymap','check_unsaved_changes')
            return km,physical,details,unsaved
        def done(data):
            self.km,self.physical,self.behaviors,unsaved=data; self.locked=False; self.render()
            self.cube.set_state('ready'); self.set_badge('●  ГОТОВА К ПРАВКАМ',GREEN)
            self.card_layers.set(str(len(self.km.layers)),'кликни клавишу для правки',flash=True)
            self.set_status_saved(unsaved)
            self.note(f'Прочитано: {len(self.km.layers)} слоёв, {len(self.behaviors)} поведений. Изменения не отправлялись.')
        self.task(read,done)

    def set_status_saved(self,unsaved):
        if unsaved:
            self.card_changes.set('ЕСТЬ ПРАВКИ','не сохранены — нажми «Сохранить»',AMBER)
        else:
            self.card_changes.set('ОТКРЫТА','всё сохранено',GREEN)

    def label(self,b):
        name=self.behaviors[b.behavior_id].display_name if b.behavior_id in self.behaviors else f'Поведение #{b.behavior_id}'
        if b.param1 in KEY_NAMES:
            return RU_KEY.get(KEY_NAMES[b.param1],KEY_NAMES[b.param1])+'  ·  '+name
        return name+('  ·  '+str(b.param1)+', '+str(b.param2) if b.param1 or b.param2 else '')

    def short_label(self,b):
        d=self.behaviors.get(b.behavior_id)
        name=(d.display_name if d else '').strip().lower()
        if b.param1 in KEY_NAMES:
            return RU_KEY.get(KEY_NAMES[b.param1],KEY_NAMES[b.param1])
        if 'momentary' in name:
            return 'Слой 1' if b.param1==1 else 'Слой %d'%b.param1
        if 'unlock' in name:
            return 'Unlock'
        if 'toggle' in name:
            return 'Tog %d'%b.param1
        if 'transparent' in name:
            return '···'
        if 'none' in name:
            return '—'
        if d is None:
            return '#%d'%b.behavior_id
        return d.display_name.strip()[:9]

    def render(self):
        for tab in self.layers.tabs(): self.layers.forget(tab)
        self.selected=None; self.clear_editor(); self.canvas_map={}
        attrs=[]
        if self.physical and self.physical.active_layout_index<len(self.physical.layouts): attrs=self.physical.layouts[self.physical.active_layout_index].keys
        for layer in self.km.layers:
            holder=tk.Frame(self.layers,bg=PANEL); self.layers.add(holder,text=layer.name or f'Слой {layer.id}')
            canvas=tk.Canvas(holder,bg=PANEL,highlightthickness=0); canvas.pack(fill='both',expand=True)
            v=ttk.Scrollbar(holder,orient='horizontal',command=canvas.xview,style='Keys.Horizontal.TScrollbar'); v.pack(fill='x'); canvas.config(xscrollcommand=v.set)
            canvas_entry=self.canvas_map.setdefault(layer.id,(canvas,{}))
            if len(attrs)!=len(layer.bindings):
                self.note(f'Слой {layer.id}: физическая раскладка не совпала — показаны позиции по порядку (без догадок).')
            positions=[]
            for i,b in enumerate(layer.bindings):
                if len(attrs)==len(layer.bindings):
                    a=attrs[i]; positions.append((a.x/100,a.y/100,max(a.width/100,.4),max(a.height/100,.4),a.r/100,a.rx/100,a.ry/100))
                else: positions.append((i%12,i//12,1,1,0,0,0))
            shapes=[]
            for x,y,w,h,r,rx,ry in positions:
                angle=math.radians(r); c,s=math.cos(angle),math.sin(angle)
                shapes.append([(rx+(px-rx)*c-(py-ry)*s,ry+(px-rx)*s+(py-ry)*c) for px,py in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]])
            minx=min((x for sh in shapes for x,y in sh),default=0); miny=min((y for sh in shapes for x,y in sh),default=0)
            scale=58
            for i,(b,shape) in enumerate(zip(layer.bindings,shapes)):
                points=[((x-minx)*scale+20,(y-miny)*scale+20) for x,y in shape]
                cx=sum(p[0] for p in points)/4; cy=sum(p[1] for p in points)/4
                inner=[(cx+(px-cx)*0.962,cy+(py-cy)*0.962) for px,py in points]
                poly=canvas.create_polygon(*[c for p in inner for c in p],fill=KEY_FILL,outline=LINE,width=2,activefill=KEY_FILL_HOVER)
                canvas_entry[1][i]=poly
                wpx=max(p[0] for p in points)-min(p[0] for p in points)
                fs=12 if wpx>=68 else (10 if wpx>=48 else 8)
                text=canvas.create_text(cx,cy-7,text=self.short_label(b),fill=TEXT,font=('Segoe UI',fs,'bold'),justify='center')
                index=canvas.create_text(cx,cy+fs,text=f'{i:02d}',fill=DIM,font=('Consolas',7))
                for item in (poly,text,index): canvas.tag_bind(item,'<Button-1>',lambda e,l=layer.id,p=i:self.select_key(l,p))
            canvas.config(scrollregion=canvas.bbox('all'))

    def select_key(self,layer_id,position):
        if self.km is None:
            self.note('Сначала нажми «Прочитать клавиатуру».')
            return
        entry=self.canvas_map.get(layer_id)
        if not entry: return
        canvas,polys=entry; poly=polys.get(position)
        if poly is None: return
        if self.key_canvas:
            try: self.key_canvas[0].itemconfig(self.key_canvas[1],fill=KEY_FILL,outline=LINE,width=2)
            except tk.TclError: pass
        self.key_canvas=(canvas,poly)
        canvas.itemconfig(poly,fill=KEY_FILL_SEL,outline=ACC,width=2)
        layer=next(l for l in self.km.layers if l.id==layer_id); old=layer.bindings[position]
        self.selected=(layer_id,position,layer)
        lname=layer.name or f'Слой {layer_id}'
        self.ed_sel.config(text=f'Слой: {lname}   ·   Клавиша: {position:02d}',fg=TEXT)
        self.ed_cur.config(text=self.label(old))
        self.ed_note.config(text='')
        self._editor_rise()

    def _editor_rise(self):
        steps=7
        def step(i):
            try:
                k=1-i/steps
                bg=blend('#1c1a28',PANEL,1-k) if k>0 else PANEL
                self.ed_sel.config(bg=bg); self.ed_cur.config(bg=bg)
                self.after(28,lambda: step(i+1))
            except tk.TclError: pass
        step(0)

    def clear_editor(self):
        self.ed_sel.config(text='Кликни по клавише слева',fg=MUTED)
        self.ed_cur.config(text='—',fg=MUTED)
        self.ed_note.config(text='')

    def find_kp_behavior(self):
        for bid,d in self.behaviors.items():
            dn=(d.display_name or '').strip().lower()
            if dn in ('key press','keypress','kp'): return bid
        return None

    def remap(self,name):
        if self.busy or not self.client or not self.selected or self.locked: return
        kp=self.find_kp_behavior()
        if kp is None:
            return messagebox.showerror('Нет поведения «Key Press»','На этой прошивке не найдено поведение ввода клавиш (kp). Переназначение недоступно.')
        layer_id,position,layer=self.selected
        binding=keymap.BehaviorBinding(behavior_id=kp,param1=KEYS[name],param2=0)
        client=self.client; lname=layer.name or f'Слой {layer_id}'; nice=palette_name(name)
        def job():
            client.set_binding(layer_id,position,binding)
            km=client.call('keymap','get_keymap')
            found=next(l for l in km.layers if l.id==layer_id).bindings[position]
            if found!=binding: raise RpcError('Клавиатура подтвердила, но результат отличается. Проверь раскладку перед сохранением.')
            return km
        def done(km):
            self.km=km; self.render()
            self.note(f'Готово: клавиша {position} (слой «{lname}») → {nice}. Ещё НЕ сохранено в память.')
            self.card_changes.set('ЕСТЬ ПРАВКИ','не сохранены — нажми «Сохранить»',AMBER,flash=True)
            self.set_badge('●  ЕСТЬ НЕСОХРАНЁННЫЕ ПРАВКИ',AMBER)
            if self.canvas_map.get(layer_id): self.select_key(layer_id,position)
            self.ed_note.config(text=f'✓  {nice} назначено и проверено. Не забудь «Сохранить в память».')
            self.ed_cur.config(text=self.label(binding))
            self.flash_key(layer_id,position)
        self.task(job,done)

    def flash_key(self,layer_id,position):
        entry=self.canvas_map.get(layer_id)
        if not entry: return
        canvas,polys=entry; poly=polys.get(position)
        if poly is None: return
        steps=10
        def step(i):
            try:
                k=abs(1-2*i/steps)
                canvas.itemconfig(poly,fill=blend(KEY_FILL,ACC,0.7*k))
                if i<steps: canvas.after(45,lambda: step(i+1))
                else: canvas.itemconfig(poly,fill=KEY_FILL_SEL)
            except tk.TclError: pass
        step(0)

    def save(self):
        if not self.client or self.busy: return
        if not messagebox.askyesno('Сохранить в память','Записать ВСЕ текущие изменения в память клавиатуры? Они останутся после выключения.'): return
        client=self.client
        def job():
            client.save()
            if client.call('keymap','check_unsaved_changes'): raise RpcError('Клавиатура подтвердила сохранение, но сообщает о несохранённых изменениях.')
        def done(_):
            self.note('Сохранено в память — клавиатура подтвердила запись.')
            self.set_badge('●  СОХРАНЕНО В ПАМЯТЬ',GREEN)
            self.card_changes.set('СОХРАНЕНО','изменения записаны навсегда',GREEN,flash=True)
            if self.selected: self.flash_key(self.selected[0],self.selected[1])
        self.task(job,done)

    def discard(self):
        if not self.client or self.busy: return
        if not messagebox.askyesno('Отменить изменения','Вернуть сохранённую раскладку? Все несохранённые правки пропадут.'): return
        client=self.client
        def job():
            if not client.call('keymap','discard_changes'): raise RpcError('Клавиатура отклонила отмену изменений')
            return client.call('keymap','get_keymap')
        def done(km):
            self.km=km; self.render(); self.note('Изменения отменены — загружена сохранённая раскладка.')
            self.card_changes.set('ОТКРЫТА','всё сохранено',GREEN,flash=True)
            self.set_badge('●  ГОТОВА К ПРАВКАМ',GREEN)
        self.task(job,done)

    def backup(self):
        if not self.km: return messagebox.showinfo('Нет данных','Сначала нажми «Прочитать клавиатуру». Резервная копия не выдумывается.')
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='petruzia-backup.json',filetypes=[('JSON','*.json')])
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f: json.dump({'keymap':MessageToDict(self.km),'physical_layouts':MessageToDict(self.physical),'behaviors':{str(i):MessageToDict(d) for i,d in self.behaviors.items()}},f,ensure_ascii=False,indent=2)
                self.note('Резервная копия сохранена: '+path)
            except OSError as exc: self.show_error(exc)

    def show_error(self,exc):
        if isinstance(exc,LockedError): self.locked=True; self.cube.set_state('locked'); self.set_badge('●  ЗАБЛОКИРОВАНА',AMBER)
        self.note('ОШИБКА: '+str(exc)); messagebox.showerror('Операция не выполнена',str(exc))
    def close(self):
        if self.client: self.client.close()
        self.destroy()

if __name__=='__main__':
    app=App()
    if '--smoke-test' in sys.argv:
        def smoke():
            assert app.client is None and app.km is None
            assert str(app.save_btn['state'])=='disabled'
            assert len(app.remap_buttons)>0
            target=sys.argv[sys.argv.index('--smoke-test')+1]
            with open(target,'w',encoding='utf-8') as f: json.dump({'native_tk':True,'window_title':app.title(),'mapped':bool(app.winfo_ismapped()),'connected':False,'hardware_writes':0,'save_disabled':True,'language':'ru','simple_remap':True,'palette_buttons':len(app.remap_buttons)},f,indent=2)
            app.close()
        app.after(500,smoke)
    app.mainloop()
