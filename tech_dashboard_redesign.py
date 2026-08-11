# -*- coding: utf-8 -*-
"""Dashboard UI redesign installed as a small runtime extension."""
import os
import customtkinter as ctk
from PIL import Image
from tech_common import THEME, get_bundle_dir
from tech_dash import PHONE_IMG_NATIVE, PHONE_SCREEN_RECT, PHONE_IMG

PHONE_SCREEN_RADIUS = 24

def _install_dashboard_redesign(self):
    page = self.pages.get('Dashboard')
    if page is None or getattr(self, '_dashboard_redesign_done', False):
        return
    self._dashboard_redesign_done = True
    # Hide the old dashboard tree; the widgets are retained for compatibility
    # with existing refresh methods, but the new layout owns the visible UI.
    for child in page.winfo_children():
        try:
            child.grid_remove()
            child.pack_forget()
        except Exception:
            pass

    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(0, weight=1)
    root = ctk.CTkFrame(page, fg_color='transparent')
    root.grid(row=0, column=0, sticky='nsew', padx=8, pady=6)
    root.grid_columnconfigure(0, weight=42, uniform='dash')
    root.grid_columnconfigure(1, weight=33, uniform='dash')
    root.grid_columnconfigure(2, weight=25, uniform='dash')
    root.grid_rowconfigure(0, weight=50, uniform='dashrow')
    root.grid_rowconfigure(1, weight=50, uniform='dashrow')

    def card(title, accent):
        f = ctk.CTkFrame(root, fg_color=THEME['panel'], corner_radius=8, border_width=1, border_color=THEME['border'])
        h = ctk.CTkFrame(f, fg_color='transparent')
        h.grid(row=0, column=0, padx=12, pady=(9, 5), sticky='ew')
        ctk.CTkLabel(h, text=title, font=ctk.CTkFont(size=10, weight='bold'), text_color=accent, anchor='w').pack(side='left')
        return f

    # Device overview / phone preview
    dev = card('📱  DEVICE OVERVIEW', THEME['green'])
    dev.grid(row=0, column=0, padx=(0,5), pady=(0,5), sticky='nsew')
    dev.grid_columnconfigure(0, weight=0); dev.grid_columnconfigure(1, weight=1); dev.grid_rowconfigure(1, weight=1)
    self.dash_conn_badge = ctk.CTkLabel(dev, text='● NO DEVICE', font=ctk.CTkFont(size=8, weight='bold'), text_color=THEME['red'])
    self.dash_conn_badge.place(relx=.98, rely=.035, anchor='ne')
    phone_col = ctk.CTkFrame(dev, fg_color='transparent', width=185)
    phone_col.grid(row=1, column=0, padx=(10,8), pady=6, sticky='ns'); phone_col.grid_propagate(False)
    ph = min(390, max(300, self.winfo_screenheight()-520)); scale = ph / 824; pw = int(396*scale)
    self.dash_phone = ctk.CTkFrame(phone_col, fg_color='transparent', width=pw, height=ph)
    self.dash_phone.pack(anchor='center'); self.dash_phone.grid_propagate(False); self.dash_phone.bind('<Configure>', self._dash_phone_configure)
    try:
        self._dash_phone_img = ctk.CTkImage(light_image=Image.open(PHONE_IMG), dark_image=Image.open(PHONE_IMG), size=(pw,ph))
        ctk.CTkLabel(self.dash_phone, image=self._dash_phone_img, text='', fg_color='transparent').place(x=0,y=0)
    except Exception: pass
    sx,sy,sw,sh = PHONE_SCREEN_RECT; cx,cy,cw,ch = [int(v*scale) for v in (sx,sy,sw,sh)]
    self._dash_log_rect=(cx,cy+int(61*scale),cw,max(1,ch-int(61*scale)))
    self._build_log_panel(self.dash_phone, place_rect=self._dash_log_rect, log_font_size=max(5,round(cw/25)), minimal=True)

    info=ctk.CTkFrame(dev,fg_color='transparent'); info.grid(row=1,column=1,padx=(2,10),pady=8,sticky='nsew'); info.grid_columnconfigure(1,weight=1)
    self._dash_vals={}
    for i,(label,key) in enumerate([('Manufacturer','brand'),('Model','model'),('Android Version','android'),('Security Patch','patch'),('Device ID','serial')]):
        ctk.CTkLabel(info,text=label,font=ctk.CTkFont(size=9),text_color=THEME['muted']).grid(row=i,column=0,padx=(0,8),pady=3,sticky='w')
        v=ctk.CTkLabel(info,text='—',font=ctk.CTkFont(size=9,weight='bold'),text_color=THEME['text']); v.grid(row=i,column=1,pady=3,sticky='ew'); self._dash_vals[key]=v
    box=ctk.CTkFrame(info,fg_color=THEME['panel2'],corner_radius=7,border_width=1,border_color=THEME['border']); box.grid(row=5,column=0,columnspan=2,pady=(8,4),sticky='ew')
    ctk.CTkLabel(box,text='DEVELOPER OPTIONS',font=ctk.CTkFont(size=9,weight='bold'),text_color=THEME['accent']).pack(anchor='w',padx=9,pady=(7,2))
    ctk.CTkLabel(box,text='Settings → About phone → Build number → Tap 7×\nDeveloper Options → USB debugging ON\n→ Connect cable → Tap “Allow” → Refresh',justify='left',font=ctk.CTkFont(size=7),text_color=THEME['muted']).pack(anchor='w',padx=9,pady=(0,7))
    leg=ctk.CTkFrame(info,fg_color='transparent'); leg.grid(row=6,column=0,columnspan=2,sticky='ew')
    for col,txt in ((THEME['green'],'Removable'),(THEME['amber'],'Clean Excluded'),(THEME['red'],'Uninstall Excluded'),('#a855f7','Both Excluded')):
        ctk.CTkLabel(leg,text=f'● {txt}',font=ctk.CTkFont(size=7),text_color=col).pack(side='left',padx=(0,7))

    # Security indicators
    sec=card('🔐  SECURITY INDICATORS',THEME['amber']); sec.grid(row=0,column=1,padx=5,pady=(0,5),sticky='nsew'); sec.grid_columnconfigure(0,weight=1); sec.grid_rowconfigure(3,weight=1)
    ctk.CTkLabel(sec,text='Security indicators found on your installed apps.',font=ctk.CTkFont(size=8),text_color=THEME['muted'],anchor='w').grid(row=1,column=0,padx=12,sticky='w')
    sm=ctk.CTkFrame(sec,fg_color='transparent'); sm.grid(row=2,column=0,padx=12,pady=5,sticky='ew')
    self.dash_security_count=ctk.CTkLabel(sm,text='🔎 Indicators Found: —',font=ctk.CTkFont(size=8,weight='bold'),text_color=THEME['amber']); self.dash_security_count.pack(side='left')
    self.dash_adware_score=ctk.CTkLabel(sm,text='  ◌ Adware Risk Score: —',font=ctk.CTkFont(size=8,weight='bold'),text_color=THEME['muted']); self.dash_adware_score.pack(side='left')
    self.dash_security_bar=ctk.CTkProgressBar(sm,width=80,height=7); self.dash_security_bar.pack(side='right'); self.dash_security_bar.set(0)
    tbl=ctk.CTkFrame(sec,fg_color=THEME['panel2'],corner_radius=7,border_width=1,border_color=THEME['border']); tbl.grid(row=3,column=0,padx=12,pady=5,sticky='nsew'); tbl.grid_columnconfigure(0,weight=1); tbl.grid_columnconfigure(1,weight=1)
    self._dash_security_rows=[]
    for i,name in enumerate(['Facebook App Manager','Package Installer','Google Gemini','Instagram','Mobile Legends']):
        ctk.CTkLabel(tbl,text=name,font=ctk.CTkFont(size=7),text_color=THEME['text']).grid(row=i,column=0,padx=7,pady=4,sticky='w')
        lab=ctk.CTkLabel(tbl,text='—',font=ctk.CTkFont(size=7),text_color=THEME['muted']); lab.grid(row=i,column=1,padx=7,pady=4,sticky='w'); self._dash_security_rows.append((name,lab))
    ctk.CTkButton(sec,text='↻ Refresh',width=80,height=26,fg_color=THEME['panel2'],hover_color=THEME['input'],border_width=1,border_color=THEME['border'],command=self._dash_refresh_click).grid(row=4,column=0,padx=12,pady=(3,8),sticky='e')

    # System info
    sysc=card('🖥  SYSTEM INFO','#14b8a6'); sysc.grid(row=0,column=2,padx=(5,0),pady=(0,5),sticky='nsew'); sysc.grid_columnconfigure(0,weight=1); self._dash_system={}
    for i,(icon,label,key) in enumerate([('🔋','Battery','battery'),('▣','Storage','storage'),('▦','RAM','ram'),('◉','CPU','cpu'),('▯','Screen','screen')]):
        b=ctk.CTkFrame(sysc,fg_color=THEME['panel2'],corner_radius=6); b.grid(row=i+1,column=0,padx=10,pady=3,sticky='ew'); b.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(b,text=icon,font=ctk.CTkFont(size=13),text_color=THEME['muted']).grid(row=0,column=0,rowspan=2,padx=7,pady=5)
        ctk.CTkLabel(b,text=label,font=ctk.CTkFont(size=7),text_color=THEME['muted']).grid(row=0,column=1,sticky='w')
        v=ctk.CTkLabel(b,text='—',font=ctk.CTkFont(size=8,weight='bold'),text_color=THEME['text']); v.grid(row=1,column=1,sticky='w',pady=(0,5)); self._dash_system[key]=v
    ctk.CTkLabel(sysc,text='More Details  →',font=ctk.CTkFont(size=8,weight='bold'),text_color=THEME['muted']).grid(row=7,column=0,padx=12,pady=8,sticky='w')

    # Running apps
    mon=card('🔎  RUNNING APPS (LIVE MONITOR)',THEME['amber']); mon.grid(row=1,column=0,padx=(0,5),pady=(5,0),sticky='nsew'); mon.grid_columnconfigure(0,weight=1); mon.grid_rowconfigure(2,weight=1)
    self.dash_monitor_events=ctk.CTkLabel(mon,text='Events: 0',font=ctk.CTkFont(size=8),text_color='#14b8a6'); self.dash_monitor_events.grid(row=0,column=0,padx=12,sticky='e')
    ctk.CTkLabel(mon,text='Live monitoring of currently running applications.',font=ctk.CTkFont(size=8),text_color=THEME['muted']).grid(row=1,column=0,padx=12,sticky='w')
    empty=ctk.CTkFrame(mon,fg_color=THEME['panel2'],corner_radius=7,border_width=1,border_color=THEME['border']); empty.grid(row=2,column=0,padx=12,pady=7,sticky='nsew')
    ctk.CTkLabel(empty,text='⌁',font=ctk.CTkFont(size=22),text_color=THEME['muted']).pack(pady=(22,2)); ctk.CTkLabel(empty,text='Click “Start Monitoring” to begin',font=ctk.CTkFont(size=9,weight='bold'),text_color=THEME['text']).pack(); ctk.CTkLabel(empty,text='Monitor foreground and background app activity\nin real-time.',justify='center',font=ctk.CTkFont(size=7),text_color=THEME['muted']).pack(pady=2)
    self.dash_monitor_btn=ctk.CTkButton(mon,text='▶  Start Monitoring',width=120,height=27,fg_color=THEME['panel2'],hover_color=THEME['input'],border_width=1,border_color=THEME['border'],command=self._dash_toggle_monitor); self.dash_monitor_btn.grid(row=3,column=0,padx=12,pady=(0,8),sticky='e')

    # VirusTotal
    vt=card('🧪  VIRUSTOTAL SCAN','#8e44ad'); vt.grid(row=1,column=1,padx=5,pady=(5,0),sticky='nsew'); vt.grid_columnconfigure(0,weight=1); vt.grid_rowconfigure(3,weight=1)
    ctk.CTkLabel(vt,text='Scan APK files with VirusTotal API.',font=ctk.CTkFont(size=8),text_color=THEME['muted']).grid(row=1,column=0,padx=12,sticky='w')
    va=ctk.CTkFrame(vt,fg_color='transparent'); va.grid(row=2,column=0,padx=12,pady=5,sticky='ew')
    ctk.CTkButton(va,text='Scan Phone',width=88,height=27,fg_color='#2980b9',command=self._dash_vt_scan).pack(side='right',padx=2); ctk.CTkButton(va,text='Pull & Upload',width=96,height=27,fg_color='#16a085',command=self._dash_vt_upload).pack(side='right',padx=2)
    box=ctk.CTkFrame(vt,fg_color=THEME['panel2'],corner_radius=7,border_width=1,border_color=THEME['border']); box.grid(row=3,column=0,padx=12,pady=5,sticky='nsew'); self.dash_vt_status=ctk.CTkLabel(box,text='No scan results yet\nChoose an option above to start scanning.',justify='center',font=ctk.CTkFont(size=8),text_color=THEME['muted']); self.dash_vt_status.pack(expand=True,fill='both')

    # DNS
    dns=card('🌐  BLOCK ADS VIA DNS','#14b8a6'); dns.grid(row=1,column=2,padx=(5,0),pady=(5,0),sticky='nsew'); dns.grid_columnconfigure(0,weight=1)
    self.dash_dns_active=ctk.CTkLabel(dns,text='Active: —',font=ctk.CTkFont(size=8,weight='bold'),text_color=THEME['green']); self.dash_dns_active.grid(row=0,column=0,padx=12,sticky='e')
    ctk.CTkLabel(dns,text='Set your private DNS server to block ads and trackers.',font=ctk.CTkFont(size=7),text_color=THEME['muted']).grid(row=1,column=0,padx=12,sticky='w')
    self.dash_dns_dropdown=ctk.CTkComboBox(dns,values=['AdGuard DNS','Cloudflare','Google DNS','Quad9'],height=27,state='readonly'); self.dash_dns_dropdown.set('AdGuard DNS'); self.dash_dns_dropdown.grid(row=2,column=0,padx=12,pady=7,sticky='ew')
    db=ctk.CTkFrame(dns,fg_color='transparent'); db.grid(row=3,column=0,padx=12,sticky='e'); ctk.CTkButton(db,text='✓ Apply DNS',width=90,height=27,fg_color='#e67e22',command=self._dash_dns_apply).pack(side='left',padx=2); ctk.CTkButton(db,text='✕ Disable',width=80,height=27,fg_color='#c0392b',command=self._dash_dns_disable).pack(side='left',padx=2)
    st=ctk.CTkFrame(dns,fg_color=THEME['panel2'],corner_radius=7,border_width=1,border_color=THEME['border']); st.grid(row=4,column=0,padx=12,pady=7,sticky='ew'); self.dash_dns_mode=ctk.CTkLabel(st,text='Mode: —\nServer: —\nStatus: —',justify='left',anchor='w',font=ctk.CTkFont(size=7),text_color=THEME['text']); self.dash_dns_mode.pack(fill='x',padx=9,pady=7)

    self.after(500,self._dash_fetch_stats)
    self.after(1000,self._dash_update_secondary)


def install_dashboard_redesign(cls):
    if getattr(cls, "_dashboard_redesign_patch_installed", False):
        return
    original = cls.build_dashboard_page
    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.after(0, lambda: _install_dashboard_redesign(self))
    cls.build_dashboard_page = wrapped
    cls._dashboard_redesign_patch_installed = True
