# -*- coding: utf-8 -*-
"""
NFC KART MALATYA
Kart satis / kira kayit, muhasebe, stok, kullanici girisi.
Tamamen yerel calisir.
"""

import os
import csv
import json
import hashlib
import sqlite3
import shutil
from datetime import datetime, date

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.checkbox import CheckBox
from kivy.utils import get_color_from_hex


# ---------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------
APP_ADI = "NFC Kart Malatya"
DB_DOSYA = "nfc_kart_malatya.db"
AYAR_DOSYA = "ayarlar.json"
YEDEK_KLASOR = "yedekler"
DISARI_KLASOR = "disa_aktar"
PARA = "TL"
KRITIK_STOK = 10

RENK_KOYU = get_color_from_hex("#1B2A41")
RENK_ORTA = get_color_from_hex("#2E4A6B")
RENK_ACIK = get_color_from_hex("#F2F4F8")
RENK_VURGU = get_color_from_hex("#E63946")
RENK_YESIL = get_color_from_hex("#2A9D8F")
RENK_SARI = get_color_from_hex("#F4A261")

Window.clearcolor = RENK_ACIK

KLASOR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------
# YARDIMCILAR
# ---------------------------------------------------------
def simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bugun():
    return date.today().strftime("%Y-%m-%d")


def _int(t, varsayilan=0):
    try:
        return int(str(t).strip())
    except (TypeError, ValueError):
        return varsayilan


def _float(t, varsayilan=0.0):
    try:
        return float(str(t).replace(",", ".").strip())
    except (TypeError, ValueError):
        return varsayilan


def kart_tutar(adet, fiyat):
    try:
        return float(adet or 0) * float(fiyat or 0)
    except (TypeError, ValueError):
        return 0.0


def popup_bilgi(baslik, mesaj):
    kutu = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    lbl = Label(text=str(mesaj), halign="center", valign="middle")
    lbl.bind(size=lambda s, *a: setattr(s, "text_size", s.size))
    kutu.add_widget(lbl)
    btn = Button(text="Tamam", size_hint_y=None, height=dp(45),
                 background_color=RENK_ORTA)
    kutu.add_widget(btn)
    pop = Popup(title=baslik, content=kutu, size_hint=(0.85, 0.45),
                title_color=RENK_KOYU, separator_color=RENK_VURGU)
    btn.bind(on_release=pop.dismiss)
    pop.open()
    return pop


def popup_onay(baslik, mesaj, onay_cb):
    kutu = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    lbl = Label(text=str(mesaj), halign="center", valign="middle")
    lbl.bind(size=lambda s, *a: setattr(s, "text_size", s.size))
    kutu.add_widget(lbl)
    b = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
    e = Button(text="Evet", background_color=RENK_YESIL)
    h = Button(text="Hayır", background_color=RENK_VURGU)
    b.add_widget(e)
    b.add_widget(h)
    kutu.add_widget(b)
    pop = Popup(title=baslik, content=kutu, size_hint=(0.85, 0.45),
                title_color=RENK_KOYU, separator_color=RENK_VURGU)

    def _e(*a):
        pop.dismiss()
        onay_cb()

    e.bind(on_release=_e)
    h.bind(on_release=pop.dismiss)
    pop.open()
    return pop


# ---------------------------------------------------------
# VERITABANI
# ---------------------------------------------------------
def db_yolu():
    return os.path.join(KLASOR, DB_DOSYA)


def baglan():
    con = sqlite3.connect(db_yolu())
    con.execute("PRAGMA foreign_keys = ON")
    return con


def tablolari_kur():
    con = baglan()
    c = con.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS kullanicilar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_adi TEXT UNIQUE NOT NULL,
        sifre_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        rol TEXT DEFAULT 'personel',
        olusturma TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS isletmeler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isletme_adi TEXT NOT NULL,
        yetkili_kisi TEXT,
        telefon TEXT,
        adres TEXT,
        kart_seri_no TEXT,
        kart_adedi INTEGER DEFAULT 0,
        birim_fiyat REAL DEFAULT 0,
        kayit_tarihi TEXT,
        son_guncelleme TEXT,
        notlar TEXT,
        aktif INTEGER DEFAULT 1
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS partiler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parti_adi TEXT NOT NULL,
        alis_tarihi TEXT,
        adet_giris INTEGER DEFAULT 0,
        adet_kalan INTEGER DEFAULT 0,
        alis_fiyat REAL DEFAULT 0,
        satis_fiyat REAL DEFAULT 0,
        tedarikci TEXT,
        notlar TEXT,
        olusturma TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS stok_hareketleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parti_id INTEGER,
        hareket TEXT NOT NULL,
        adet INTEGER NOT NULL,
        birim_fiyat REAL DEFAULT 0,
        isletme_id INTEGER,
        tarih TEXT NOT NULL,
        aciklama TEXT,
        FOREIGN KEY (parti_id) REFERENCES partiler(id) ON DELETE SET NULL,
        FOREIGN KEY (isletme_id) REFERENCES isletmeler(id) ON DELETE SET NULL
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS islemler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isletme_id INTEGER NOT NULL,
        parti_id INTEGER,
        islem_turu TEXT NOT NULL,
        tutar REAL DEFAULT 0,
        adet INTEGER DEFAULT 0,
        tarih TEXT NOT NULL,
        aciklama TEXT,
        FOREIGN KEY (isletme_id) REFERENCES isletmeler(id) ON DELETE CASCADE,
        FOREIGN KEY (parti_id) REFERENCES partiler(id) ON DELETE SET NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_islem_isletme ON islemler(isletme_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_islem_tarih ON islemler(tarih)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_hareket_parti ON stok_hareketleri(parti_id)")
    con.commit()
    con.close()


# ---------------------------------------------------------
# KULLANICI
# ---------------------------------------------------------
def hash_sifre(sifre, salt=None):
    if salt is None:
        salt = hashlib.sha256(os.urandom(16)).hexdigest()
    h = hashlib.sha256((salt + sifre).encode("utf-8")).hexdigest()
    return h, salt


def sifre_dogrula(sifre, h, salt):
    yeni, _ = hash_sifre(sifre, salt)
    return yeni == h


def kullanici_var_mi():
    con = baglan()
    n = con.execute("SELECT COUNT(*) FROM kullanicilar").fetchone()[0]
    con.close()
    return n > 0


def kullanici_ekle(kadi, sifre, rol="personel"):
    h, s = hash_sifre(sifre)
    con = baglan()
    con.execute(
        "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, salt, rol, olusturma)"
        " VALUES (?,?,?,?,?)",
        (kadi, h, s, rol, simdi())
    )
    con.commit()
    con.close()


def kullanici_bul(kadi):
    con = baglan()
    k = con.execute("SELECT * FROM kullanicilar WHERE kullanici_adi=?", (kadi,)).fetchone()
    con.close()
    return k


def tum_kullanicilar():
    con = baglan()
    k = con.execute("SELECT id, kullanici_adi, rol, olusturma FROM kullanicilar ORDER BY id").fetchall()
    con.close()
    return k


def kullanici_sil(kid):
    con = baglan()
    hedef = con.execute("SELECT rol FROM kullanicilar WHERE id=?", (kid,)).fetchone()
    if hedef and hedef[0] == "yonetici":
        n = con.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol='yonetici'").fetchone()[0]
        if n <= 1:
            con.close()
            return False, "Son yonetici silinemez."
    con.execute("DELETE FROM kullanicilar WHERE id=?", (kid,))
    con.commit()
    con.close()
    return True, "Silindi."


# ---------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------
def ayar_oku():
    yol = os.path.join(KLASOR, AYAR_DOSYA)
    if os.path.isfile(yol):
        try:
            with open(yol, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def ayar_yaz(d):
    yol = os.path.join(KLASOR, AYAR_DOSYA)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# =========================================================
# GIRIS EKRANI
# =========================================================
class GirisEkrani(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.olustur()

    def olustur(self):
        self.clear_widgets()
        kok = BoxLayout(orientation="vertical", padding=dp(40), spacing=dp(14))

        kok.add_widget(Label(
            text="[b]NFC KART MALATYA[/b]", markup=True,
            font_size="28sp", color=RENK_KOYU,
            size_hint_y=None, height=dp(70)
        ))

        if not kullanici_var_mi():
            kok.add_widget(Label(
                text="Ilk kurulum: Yonetici hesabi olusturun",
                color=RENK_VURGU, font_size="16sp",
                size_hint_y=None, height=dp(40)
            ))
            self.kadi = TextInput(hint_text="Kullanici adi (orn: admin)",
                                  multiline=False, size_hint_y=None, height=dp(50))
            self.sifre1 = TextInput(hint_text="Sifre", password=True,
                                    multiline=False, size_hint_y=None, height=dp(50))
            self.sifre2 = TextInput(hint_text="Sifre (tekrar)", password=True,
                                    multiline=False, size_hint_y=None, height=dp(50))
            kok.add_widget(self.kadi)
            kok.add_widget(self.sifre1)
            kok.add_widget(self.sifre2)

            btn = Button(text="Hesabi Olustur", size_hint_y=None, height=dp(55),
                         background_color=RENK_YESIL)
            btn.bind(on_release=self.kur)
            kok.add_widget(btn)
        else:
            kok.add_widget(Label(text="Giris yapin", color=RENK_KOYU,
                                 font_size="18sp", size_hint_y=None, height=dp(40)))
            self.kadi = TextInput(hint_text="Kullanici adi", multiline=False,
                                  size_hint_y=None, height=dp(50))
            self.sifre1 = TextInput(hint_text="Sifre", password=True,
                                    multiline=False, size_hint_y=None, height=dp(50))
            kok.add_widget(self.kadi)
            kok.add_widget(self.sifre1)

            hk = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
            hk.add_widget(Label(text="Beni hatirla", color=RENK_KOYU))
            self.hatirla = CheckBox(active=ayar_oku().get("beni_hatirla", False))
            hk.add_widget(self.hatirla)
            kok.add_widget(hk)

            btn = Button(text="Giris", size_hint_y=None, height=dp(55),
                         background_color=RENK_YESIL)
            btn.bind(on_release=self.giris)
            kok.add_widget(btn)

        self.add_widget(kok)

    def kur(self, *a):
        kadi = self.kadi.text.strip()
        s1 = self.sifre1.text
        s2 = self.sifre2.text
        if not kadi or len(s1) < 4:
            popup_bilgi("Hata", "Kullanici adi ve en az 4 karakter sifre gerekli.")
            return
        if s1 != s2:
            popup_bilgi("Hata", "Sifreler uyusmuyor.")
            return
        try:
            kullanici_ekle(kadi, s1, "yonetici")
        except sqlite3.IntegrityError:
            popup_bilgi("Hata", "Bu kullanici zaten var.")
            return
        popup_bilgi("Basarili", "Yonetici olusturuldu. Simdi giris yapin.")
        self.olustur()

    def giris(self, *a):
        kadi = self.kadi.text.strip()
        sifre = self.sifre1.text
        k = kullanici_bul(kadi)
        if not k or not sifre_dogrula(sifre, k[2], k[3]):
            popup_bilgi("Hata", "Kullanici adi veya sifre hatali.")
            return

        app = App.get_running_app()
        app.aktif_kullanici = {"id": k[0], "kadi": k[1], "rol": k[4]}

        hatirla = bool(self.hatirla.active) if hasattr(self, "hatirla") else False
        a = ayar_oku()
        a["beni_hatirla"] = hatirla
        a["son_kullanici"] = kadi if hatirla else ""
        ayar_yaz(a)

        app.root.current = "ana"
        Clock.schedule_once(lambda dt: app.root.get_screen("ana").yenile(), 0.2)


# =========================================================
# ANA EKRAN
# =========================================================
class AnaEkran(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.olustur()

    def olustur(self):
        self.clear_widgets()
        kok = BoxLayout(orientation="vertical")

        ust = BoxLayout(size_hint_y=None, height=dp(50), padding=dp(6), spacing=dp(6))
        ust.add_widget(Label(text="[b]NFC KART MALATYA[/b]", markup=True,
                             font_size="18sp", color=RENK_KOYU, size_hint_x=0.6))
        self.klbl = Label(text="", color=RENK_ORTA, size_hint_x=0.25)
        ust.add_widget(self.klbl)
        cikis = Button(text="Cikis", size_hint_x=0.15, background_color=RENK_VURGU)
        cikis.bind(on_release=self.cikis)
        ust.add_widget(cikis)
        kok.add_widget(ust)

        self.tab = TabbedPanel(do_default_tab=False, tab_width=dp(140))
        self.tab.background_color = RENK_ACIK

        self.form = IsletmeFormu()
        self.form.b_kaydet.bind(on_release=self.kaydet)
        self.form.b_guncelle.bind(on_release=self.guncelle)
        self.form.b_temizle.bind(on_release=lambda *a: self.form.temizle())
        t1 = TabbedPanelItem(text="Kayit")
        t1.add_widget(self.form)
        self.tab.add_widget(t1)

        self.liste = IsletmeListesi()
        self.liste.detay_cb = self.detay_ac
        t2 = TabbedPanelItem(text="Isletmeler")
        t2.add_widget(self.liste)
        self.tab.add_widget(t2)

        self.islem = IslemFormu()
        t3 = TabbedPanelItem(text="Tahsilat/Satis")
        t3.add_widget(self.islem)
        self.tab.add_widget(t3)

        self.parti = PartiPaneli()
        t4 = TabbedPanelItem(text="Stok")
        t4.add_widget(self.parti)
        self.tab.add_widget(t4)

        self.muhasebe = MuhasebePaneli()
        t5 = TabbedPanelItem(text="Muhasebe")
        t5.add_widget(self.muhasebe)
        self.tab.add_widget(t5)

        self.disa = DisaAktarPaneli()
        t6 = TabbedPanelItem(text="Disa Aktar")
        t6.add_widget(self.disa)
        self.tab.add_widget(t6)

        self.yedek = YedekPaneli()
        t7 = TabbedPanelItem(text="Yedek")
        t7.add_widget(self.yedek)
        self.tab.add_widget(t7)

        self.kullanicilar = KullaniciPaneli()
        t8 = TabbedPanelItem(text="Kullanicilar")
        t8.add_widget(self.kullanicilar)
        self.tab.add_widget(t8)

        kok.add_widget(self.tab)
        self.add_widget(kok)

    def yenile(self):
        app = App.get_running_app()
        k = getattr(app, "aktif_kullanici", None)
        if k:
            self.klbl.text = "%s (%s)" % (k["kadi"], k["rol"])
        try:
            self.liste.yenile()
            self.islem.isletmeleri_yukle()
            self.form.partileri_yukle()
            self.parti.listele()
        except Exception as e:
            print("Yenileme hatasi:", e)

    def sekme_sec(self, index):
        try:
            self.tab.switch_to(self.tab.tab_list[-(index + 1)])
        except Exception:
            pass

    def kaydet(self, *a):
        v = self.form.veri_al()
        if not v["isletme_adi"]:
            popup_bilgi("Uyari", "Isletme adi zorunludur.")
            return
        parti = v["parti"]
        con = baglan()
        c = con.cursor()
        c.execute(
            "INSERT INTO isletmeler (isletme_adi, yetkili_kisi, telefon, adres,"
            " kart_seri_no, kart_adedi, birim_fiyat, kayit_tarihi, son_guncelleme, notlar)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (v["isletme_adi"], v["yetkili_kisi"], v["telefon"], v["adres"],
             v["kart_seri_no"], v["kart_adedi"], v["birim_fiyat"],
             simdi(), simdi(), v["notlar"])
        )
        isletme_id = c.lastrowid

        if parti and v["kart_adedi"] > 0:
            if parti["kalan"] < v["kart_adedi"]:
                con.rollback()
                con.close()
                popup_bilgi("Stok Yetersiz",
                            "Bu partide yeterli kart yok (kalan: %d)." % parti["kalan"])
                return
            c.execute("UPDATE partiler SET adet_kalan=adet_kalan-? WHERE id=?",
                      (v["kart_adedi"], parti["id"]))
            c.execute(
                "INSERT INTO stok_hareketleri (parti_id, hareket, adet, birim_fiyat,"
                " isletme_id, tarih, aciklama) VALUES (?,?,?,?,?,?,?)",
                (parti["id"], "cikis", v["kart_adedi"], parti["fiyat"],
                 isletme_id, simdi(), "Kayit: " + v["isletme_adi"])
            )
        con.commit()
        con.close()
        self.form.temizle()
        self.form.partileri_yukle()
        self.liste.yenile()
        self.islem.isletmeleri_yukle()
        self.parti.listele()
        popup_bilgi("Basarili", "Isletme kaydedildi.")

    def guncelle(self, *a):
        if not self.form.secili_id:
            popup_bilgi("Uyari", "Listeden kayit secip 'Duzenle' deyin.")
            return
        v = self.form.veri_al()
        if not v["isletme_adi"]:
            popup_bilgi("Uyari", "Isletme adi zorunludur.")
            return
        con = baglan()
        con.execute(
            "UPDATE isletmeler SET isletme_adi=?, yetkili_kisi=?, telefon=?,"
            " adres=?, kart_seri_no=?, kart_adedi=?, birim_fiyat=?,"
            " son_guncelleme=?, notlar=? WHERE id=?",
            (v["isletme_adi"], v["yetkili_kisi"], v["telefon"], v["adres"],
             v["kart_seri_no"], v["kart_adedi"], v["birim_fiyat"],
             simdi(), v["notlar"], self.form.secili_id)
        )
        con.commit()
        con.close()
        self.form.temizle()
        self.liste.yenile()
        self.islem.isletmeleri_yukle()
        popup_bilgi("Basarili", "Kayit guncellendi.")

    def detay_ac(self, isletme_id):
        p = DetayPenceresi(isletme_id, yenile_cb=self._detay_sonrasi)
        pop = Popup(title="Isletme Detayi", content=p, size_hint=(0.95, 0.9),
                    title_color=RENK_KOYU, separator_color=RENK_VURGU)
        p._popup = pop
        pop.open()

    def _detay_sonrasi(self):
        self.liste.yenile(self.liste.arama.text)
        self.islem.isletmeleri_yukle()

    def cikis(self, *a):
        App.get_running_app().aktif_kullanici = None
        app = App.get_running_app()
        g = app.root.get_screen("giris")
        g.olustur()
        app.root.current = "giris"


# =========================================================
# ISLETME FORMU
# =========================================================
class IsletmeFormu(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)

        self.add_widget(Label(text="[b]ISLETME KAYDI[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))

        form = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        self.g = {}
        for etiket in ["Isletme Adi", "Yetkili Kisi", "Telefon", "Adres",
                       "Kart Seri No", "Kart Adedi", "Birim Fiyat", "Notlar"]:
            form.add_widget(Label(text=etiket, color=RENK_KOYU,
                                  size_hint_y=None, height=dp(40)))
            ti = TextInput(multiline=False, size_hint_y=None, height=dp(40))
            self.g[etiket] = ti
            form.add_widget(ti)
        self.add_widget(form)

        pform = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(45))
        pform.add_widget(Label(text="Kart Partisi", color=RENK_KOYU))
        self.parti_spinner = Spinner(text="Seciniz", values=[])
        pform.add_widget(self.parti_spinner)
        self.add_widget(pform)

        bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        self.b_kaydet = Button(text="Kaydet", background_color=RENK_YESIL)
        self.b_guncelle = Button(text="Guncelle", background_color=RENK_ORTA)
        self.b_temizle = Button(text="Temizle", background_color=RENK_VURGU)
        bar.add_widget(self.b_kaydet)
        bar.add_widget(self.b_guncelle)
        bar.add_widget(self.b_temizle)
        self.add_widget(bar)

        self.secili_id = None
        self.parti_harita = {}
        self.partileri_yukle()

    def partileri_yukle(self):
        con = baglan()
        kayitlar = con.execute(
            "SELECT id, parti_adi, adet_kalan, satis_fiyat FROM partiler"
            " WHERE adet_kalan>0 ORDER BY id DESC"
        ).fetchall()
        con.close()
        self.parti_harita = {}
        for k in kayitlar:
            anahtar = "#%d %s (kalan:%d, %.2f %s)" % (k[0], k[1], k[2], k[3], PARA)
            self.parti_harita[anahtar] = {"id": k[0], "kalan": k[2], "fiyat": k[3]}
        self.parti_spinner.values = list(self.parti_harita.keys())
        if self.parti_harita:
            self.parti_spinner.text = list(self.parti_harita.keys())[0]
        else:
            self.parti_spinner.text = "Seciniz"

    def temizle(self):
        for ti in self.g.values():
            ti.text = ""
        self.secili_id = None

    def doldur(self, kayit):
        self.g["Isletme Adi"].text = kayit[1] or ""
        self.g["Yetkili Kisi"].text = kayit[2] or ""
        self.g["Telefon"].text = kayit[3] or ""
        self.g["Adres"].text = kayit[4] or ""
        self.g["Kart Seri No"].text = kayit[5] or ""
        self.g["Kart Adedi"].text = str(kayit[6] or "")
        self.g["Birim Fiyat"].text = str(kayit[7] or "")
        self.g["Notlar"].text = kayit[10] or ""
        self.secili_id = kayit[0]

    def veri_al(self):
        return {
            "isletme_adi": self.g["Isletme Adi"].text.strip(),
            "yetkili_kisi": self.g["Yetkili Kisi"].text.strip(),
            "telefon": self.g["Telefon"].text.strip(),
            "adres": self.g["Adres"].text.strip(),
            "kart_seri_no": self.g["Kart Seri No"].text.strip(),
            "kart_adedi": _int(self.g["Kart Adedi"].text),
            "birim_fiyat": _float(self.g["Birim Fiyat"].text),
            "notlar": self.g["Notlar"].text.strip(),
            "parti": self.parti_harita.get(self.parti_spinner.text),
        }


# =========================================================
# ISLETME LISTESI
# =========================================================
class IsletmeListesi(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.detay_cb = None

        ust = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        ust.add_widget(Label(text="Ara:", size_hint_x=0.15, color=RENK_KOYU))
        self.arama = TextInput(multiline=False, hint_text="Isletme / yetkili / telefon")
        ust.add_widget(self.arama)
        ba = Button(text="Ara", size_hint_x=0.2, background_color=RENK_ORTA)
        ba.bind(on_release=lambda *a: self.yenile(self.arama.text))
        bt = Button(text="Tumu", size_hint_x=0.2, background_color=RENK_KOYU)

        def _tumu(*a):
            self.arama.text = ""
            self.yenile("")

        bt.bind(on_release=_tumu)
        ust.add_widget(ba)
        ust.add_widget(bt)
        self.add_widget(ust)

        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)

    def yenile(self, filtre=""):
        self.ic.clear_widgets()
        con = baglan()
        if filtre:
            f = "%" + filtre + "%"
            kayitlar = con.execute(
                "SELECT id, isletme_adi, yetkili_kisi, telefon, kart_adedi,"
                " birim_fiyat, aktif FROM isletmeler"
                " WHERE isletme_adi LIKE ? OR yetkili_kisi LIKE ? OR telefon LIKE ?"
                " ORDER BY id DESC", (f, f, f)
            ).fetchall()
        else:
            kayitlar = con.execute(
                "SELECT id, isletme_adi, yetkili_kisi, telefon, kart_adedi,"
                " birim_fiyat, aktif FROM isletmeler ORDER BY id DESC"
            ).fetchall()
        con.close()

        if not kayitlar:
            self.ic.add_widget(Label(text="Kayit bulunamadi.", color=RENK_VURGU,
                                     size_hint_y=None, height=dp(40)))
            return

        for k in kayitlar:
            renk = RENK_YESIL if k[6] else RENK_VURGU
            metin = ("[b]%s[/b]\nYetkili: %s  |  Tel: %s\nKart: %d  |  Birim: %s %s" %
                     (k[1], k[2] or "-", k[3] or "-", k[4] or 0, k[5] or 0, PARA))
            satir = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(6))
            lbl = Label(text=metin, markup=True, halign="left", valign="middle",
                        color=RENK_KOYU, size_hint_x=0.75)
            lbl.bind(size=lambda s, *a: setattr(s, "text_size", s.size))
            satir.add_widget(lbl)
            btn = Button(text="Detay", size_hint_x=0.25, background_color=renk)
            btn.bind(on_release=lambda *a, kid=k[0]: self.detay_cb and self.detay_cb(kid))
            satir.add_widget(btn)
            self.ic.add_widget(satir)


# =========================================================
# ISLEM FORMU
# =========================================================
class IslemFormu(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.id_harita = {}

        self.add_widget(Label(text="[b]TAHSILAT / SATIS[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))

        form = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(Label(text="Isletme", color=RENK_KOYU, size_hint_y=None, height=dp(40)))
        self.isletme_spinner = Spinner(text="Seciniz", values=[],
                                       size_hint_y=None, height=dp(40))
        form.add_widget(self.isletme_spinner)

        form.add_widget(Label(text="Islem Turu", color=RENK_KOYU, size_hint_y=None, height=dp(40)))
        self.tur_spinner = Spinner(text="tahsilat",
                                   values=("tahsilat", "satis", "guncelleme", "iade"),
                                   size_hint_y=None, height=dp(40))
        form.add_widget(self.tur_spinner)

        form.add_widget(Label(text="Adet (satis icin)", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        self.adet = TextInput(multiline=False, size_hint_y=None, height=dp(40))
        form.add_widget(self.adet)

        form.add_widget(Label(text="Tutar", color=RENK_KOYU, size_hint_y=None, height=dp(40)))
        self.tutar = TextInput(multiline=False, size_hint_y=None, height=dp(40))
        form.add_widget(self.tutar)

        form.add_widget(Label(text="Tarih", color=RENK_KOYU, size_hint_y=None, height=dp(40)))
        self.tarih = TextInput(text=bugun(), multiline=False,
                               size_hint_y=None, height=dp(40))
        form.add_widget(self.tarih)

        form.add_widget(Label(text="Aciklama", color=RENK_KOYU, size_hint_y=None, height=dp(40)))
        self.aciklama = TextInput(multiline=False, size_hint_y=None, height=dp(40))
        form.add_widget(self.aciklama)
        self.add_widget(form)

        b = Button(text="Islemi Kaydet", size_hint_y=None, height=dp(50),
                   background_color=RENK_YESIL)
        b.bind(on_release=self.kaydet)
        self.add_widget(b)

        self.isletmeleri_yukle()

    def isletmeleri_yukle(self):
        con = baglan()
        kayitlar = con.execute(
            "SELECT id, isletme_adi FROM isletmeler WHERE aktif=1 ORDER BY isletme_adi"
        ).fetchall()
        con.close()
        self.id_harita = {"%s (#%d)" % (k[1], k[0]): k[0] for k in kayitlar}
        self.isletme_spinner.values = list(self.id_harita.keys())
        if self.id_harita:
            self.isletme_spinner.text = list(self.id_harita.keys())[0]

    def kaydet(self, *a):
        secim = self.isletme_spinner.text
        if secim not in self.id_harita:
            popup_bilgi("Hata", "Isletme secin.")
            return
        isletme_id = self.id_harita[secim]
        tur = self.tur_spinner.text
        tutar = _float(self.tutar.text)
        adet = _int(self.adet.text)
        tarih = self.tarih.text.strip() or bugun()
        aciklama = self.aciklama.text.strip()

        con = baglan()
        c = con.cursor()
        parti_id = None

        if tur == "satis" and adet > 0:
            p = c.execute(
                "SELECT id, adet_kalan, satis_fiyat FROM partiler"
                " WHERE adet_kalan>=? ORDER BY id ASC LIMIT 1", (adet,)
            ).fetchone()
            if not p:
                con.close()
                popup_bilgi("Stok Yetersiz", "Yeterli stokta parti yok (istenen: %d)." % adet)
                return
            parti_id = p[0]
            c.execute("UPDATE partiler SET adet_kalan=adet_kalan-? WHERE id=?",
                      (adet, parti_id))
            c.execute(
                "INSERT INTO stok_hareketleri (parti_id, hareket, adet, birim_fiyat,"
                " isletme_id, tarih, aciklama) VALUES (?,?,?,?,?,?,?)",
                (parti_id, "cikis", adet, p[2], isletme_id, tarih,
                 aciklama or "Satis")
            )
            if tutar == 0:
                tutar = adet * (p[2] or 0)

        if tur == "iade" and adet > 0:
            p = c.execute("SELECT id FROM partiler ORDER BY id DESC LIMIT 1").fetchone()
            if p:
                parti_id = p[0]
                c.execute("UPDATE partiler SET adet_kalan=adet_kalan+? WHERE id=?",
                          (adet, parti_id))
                c.execute(
                    "INSERT INTO stok_hareketleri (parti_id, hareket, adet,"
                    " isletme_id, tarih, aciklama) VALUES (?,?,?,?,?,?)",
                    (parti_id, "giris", adet, isletme_id, tarih,
                     aciklama or "Iade")
                )

        c.execute(
            "INSERT INTO islemler (isletme_id, parti_id, islem_turu, tutar, adet,"
            " tarih, aciklama) VALUES (?,?,?,?,?,?,?)",
            (isletme_id, parti_id, tur, tutar, adet, tarih, aciklama)
        )
        con.commit()
        con.close()

        self.tutar.text = ""
        self.adet.text = ""
        self.aciklama.text = ""
        app = App.get_running_app()
        ana = app.root.get_screen("ana")
        ana.parti.listele()
        ana.form.partileri_yukle()
        popup_bilgi("Basarili", "Islem kaydedildi.")


# =========================================================
# PARTI / STOK PANELI
# =========================================================
class PartiPaneli(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)

        self.add_widget(Label(text="[b]KART PARTILERI / STOK[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))

        form = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        self.g = {}
        for etiket in ["Parti Adi", "Alis Tarihi", "Adet",
                       "Alis Fiyati", "Satis Fiyati", "Tedarikci", "Notlar"]:
            form.add_widget(Label(text=etiket, color=RENK_KOYU,
                                  size_hint_y=None, height=dp(38)))
            ti = TextInput(multiline=False, size_hint_y=None, height=dp(38))
            if etiket == "Alis Tarihi":
                ti.text = bugun()
            self.g[etiket] = ti
            form.add_widget(ti)
        self.add_widget(form)

        bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        b1 = Button(text="Parti Ekle", background_color=RENK_YESIL)
        b1.bind(on_release=self.parti_ekle)
        b2 = Button(text="Stok Duzelt", background_color=RENK_ORTA)
        b2.bind(on_release=self.manuel_giris)
        b3 = Button(text="Yenile", background_color=RENK_KOYU)
        b3.bind(on_release=lambda *a: self.listele())
        bar.add_widget(b1)
        bar.add_widget(b2)
        bar.add_widget(b3)
        self.add_widget(bar)

        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)

        self.listele()

    def parti_ekle(self, *a):
        g = self.g
        adi = g["Parti Adi"].text.strip()
        if not adi:
            popup_bilgi("Uyari", "Parti adi zorunludur.")
            return
        adet = _int(g["Adet"].text)
        if adet <= 0:
            popup_bilgi("Uyari", "Adet 0'dan buyuk olmali.")
            return
        af = _float(g["Alis Fiyati"].text)
        sf = _float(g["Satis Fiyati"].text)

        con = baglan()
        c = con.cursor()
        c.execute(
            "INSERT INTO partiler (parti_adi, alis_tarihi, adet_giris, adet_kalan,"
            " alis_fiyat, satis_fiyat, tedarikci, notlar, olusturma)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (adi, g["Alis Tarihi"].text.strip() or bugun(), adet, adet,
             af, sf, g["Tedarikci"].text.strip(), g["Notlar"].text.strip(), simdi())
        )
        pid = c.lastrowid
        c.execute(
            "INSERT INTO stok_hareketleri (parti_id, hareket, adet, birim_fiyat,"
            " tarih, aciklama) VALUES (?,?,?,?,?,?)",
            (pid, "giris", adet, af, simdi(), "Yeni parti: " + adi)
        )
        con.commit()
        con.close()
        for k, ti in self.g.items():
            if k != "Alis Tarihi":
                ti.text = ""
        self.listele()
        popup_bilgi("Basarili", "'%s' partisi eklendi. Stok: %d" % (adi, adet))

    def manuel_giris(self, *a):
        kutu = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        kutu.add_widget(Label(text="Parti ID ve adet girin (stok duzeltmesi)"))
        pid_ti = TextInput(hint_text="Parti ID", multiline=False,
                           size_hint_y=None, height=dp(40))
        adet_ti = TextInput(hint_text="+ / - adet (orn: -3 veya 5)",
                            multiline=False, size_hint_y=None, height=dp(40))
        aciklama_ti = TextInput(hint_text="Aciklama", multiline=False,
                                size_hint_y=None, height=dp(40))
        kutu.add_widget(pid_ti)
        kutu.add_widget(adet_ti)
        kutu.add_widget(aciklama_ti)

        pop = Popup(title="Manuel Stok Hareketi", content=kutu,
                    size_hint=(0.85, 0.55), title_color=RENK_KOYU,
                    separator_color=RENK_VURGU)

        def _kaydet(*a):
            pid = _int(pid_ti.text)
            adet = _int(adet_ti.text)
            if pid <= 0 or adet == 0:
                popup_bilgi("Hata", "Parti ID ve sifirdan farkli adet gerekli.")
                return
            con = baglan()
            p = con.execute("SELECT adet_kalan FROM partiler WHERE id=?", (pid,)).fetchone()
            if not p:
                con.close()
                popup_bilgi("Hata", "Parti bulunamadi.")
                return
            yeni = p[0] + adet
            if yeni < 0:
                con.close()
                popup_bilgi("Hata", "Stok negatife dusemez.")
                return
            con.execute("UPDATE partiler SET adet_kalan=? WHERE id=?", (yeni, pid))
            con.execute(
                "INSERT INTO stok_hareketleri (parti_id, hareket, adet, tarih, aciklama)"
                " VALUES (?,?,?,?,?)",
                (pid, "giris" if adet > 0 else "cikis", abs(adet),
                 simdi(), aciklama_ti.text.strip() or "Manuel duzeltme")
            )
            con.commit()
            con.close()
            pop.dismiss()
            self.listele()
            popup_bilgi("Basarili", "Stok guncellendi. Yeni kalan: %d" % yeni)

        b = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(8))
        be = Button(text="Kaydet", background_color=RENK_YESIL)
        be.bind(on_release=_kaydet)
        bh = Button(text="Iptal", background_color=RENK_VURGU)
        bh.bind(on_release=pop.dismiss)
        b.add_widget(be)
        b.add_widget(bh)
        kutu.add_widget(b)
        pop.open()

    def listele(self):
        self.ic.clear_widgets()
        con = baglan()
        kayitlar = con.execute(
            "SELECT id, parti_adi, alis_tarihi, adet_giris, adet_kalan,"
            " alis_fiyat, satis_fiyat, tedarikci FROM partiler ORDER BY id DESC"
        ).fetchall()
        con.close()
        if not kayitlar:
            self.ic.add_widget(Label(text="Henuz parti eklenmedi.", color=RENK_VURGU,
                                     size_hint_y=None, height=dp(40)))
            return
        for k in kayitlar:
            kritik = k[4] <= KRITIK_STOK
            renk = RENK_VURGU if kritik else RENK_YESIL
            renk_hex = "E63946" if kritik else "2A9D8F"
            metin = ("[b]#%d %s[/b]  (%s)\n"
                     "Giris: %d  |  Kalan: [color=%s]%d[/color]"
                     "  |  Alis: %.2f  |  Satis: %.2f %s\nTedarikci: %s" %
                     (k[0], k[1], k[2], k[3], renk_hex, k[4],
                      k[5] or 0, k[6] or 0, PARA, k[7] or "-"))
            satir = BoxLayout(size_hint_y=None, height=dp(75), spacing=dp(6))
            lbl = Label(text=metin, markup=True, halign="left", valign="middle",
                        color=RENK_KOYU, size_hint_x=0.75)
            lbl.bind(size=lambda s, *a: setattr(s, "text_size", s.size))
            satir.add_widget(lbl)
            btn = Button(text="Hareketler", size_hint_x=0.25, background_color=renk)
            btn.bind(on_release=lambda *a, pid=k[0]: self.hareketler(pid))
            satir.add_widget(btn)
            self.ic.add_widget(satir)

    def hareketler(self, pid):
        con = baglan()
        kayitlar = con.execute(
            "SELECT tarih, hareket, adet, aciklama FROM stok_hareketleri"
            " WHERE parti_id=? ORDER BY id DESC", (pid,)
        ).fetchall()
        p = con.execute("SELECT parti_adi FROM partiler WHERE id=?", (pid,)).fetchone()
        con.close()

        kutu = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        baslik = p[0] if p else str(pid)
        kutu.add_widget(Label(text="[b]%s - Stok Hareketleri[/b]" % baslik,
                              markup=True, color=RENK_KOYU,
                              size_hint_y=None, height=dp(30)))
        sv = ScrollView()
        ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(3))
        ic.bind(minimum_height=ic.setter("height"))
        if not kayitlar:
            ic.add_widget(Label(text="Hareket yok.", color=RENK_VURGU,
                                size_hint_y=None, height=dp(30)))
        else:
            for k in kayitlar:
                ic.add_widget(Label(
                    text="%s | %s | %d | %s" % (k[0], k[1], k[2], k[3] or ""),
                    color=RENK_KOYU, size_hint_y=None, height=dp(30)))
        sv.add_widget(ic)
        kutu.add_widget(sv)
        b = Button(text="Kapat", size_hint_y=None, height=dp(40),
                   background_color=RENK_KOYU)
        pop = Popup(title="Stok Hareketleri", content=kutu, size_hint=(0.9, 0.8),
                    title_color=RENK_KOYU, separator_color=RENK_VURGU)
        b.bind(on_release=pop.dismiss)
        kutu.add_widget(b)
        pop.open()


# =========================================================
# MUHASEBE
# =========================================================
class MuhasebePaneli(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.add_widget(Label(text="[b]MUHASEBE & RAPOR[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))

        f = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, height=dp(80))
        f.add_widget(Label(text="Baslangic", color=RENK_KOYU))
        self.bas = TextInput(text=bugun()[:8] + "01", multiline=False)
        f.add_widget(self.bas)
        f.add_widget(Label(text="Bitis", color=RENK_KOYU))
        self.bit = TextInput(text=bugun(), multiline=False)
        f.add_widget(self.bit)
        self.add_widget(f)

        bar = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        for t, cb, rk in [("Ozet", self.ozet, RENK_ORTA),
                          ("Dokum", self.dokum, RENK_ORTA),
                          ("Borc", self.borclular, RENK_VURGU),
                          ("Stok Deger", self.stok_deger, RENK_YESIL)]:
            b = Button(text=t, background_color=rk)
            b.bind(on_release=cb)
            bar.add_widget(b)
        self.add_widget(bar)

        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)

    def _yaz(self, satirlar):
        self.ic.clear_widgets()
        for s in satirlar:
            lbl = Label(text=s, markup=True, halign="left", valign="top",
                        color=RENK_KOYU, size_hint_y=None)
            lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
            lbl.bind(texture_size=lambda i, ts: setattr(i, "height", ts[1] + dp(6)))
            self.ic.add_widget(lbl)

    def ozet(self, *a):
        bas, bit = self.bas.text.strip(), self.bit.text.strip()
        con = baglan()
        c = con.cursor()
        n = c.execute("SELECT COUNT(*) FROM isletmeler").fetchone()[0]
        kart = c.execute("SELECT COALESCE(SUM(kart_adedi),0) FROM isletmeler").fetchone()[0]
        pot = c.execute("SELECT COALESCE(SUM(kart_adedi*birim_fiyat),0) FROM isletmeler").fetchone()[0]
        t = c.execute("SELECT COALESCE(SUM(tutar),0) FROM islemler"
                      " WHERE islem_turu='tahsilat' AND tarih BETWEEN ? AND ?",
                      (bas, bit)).fetchone()[0]
        s = c.execute("SELECT COALESCE(SUM(tutar),0) FROM islemler"
                      " WHERE islem_turu='satis' AND tarih BETWEEN ? AND ?",
                      (bas, bit)).fetchone()[0]
        i = c.execute("SELECT COALESCE(SUM(tutar),0) FROM islemler"
                      " WHERE islem_turu='iade' AND tarih BETWEEN ? AND ?",
                      (bas, bit)).fetchone()[0]
        con.close()
        net = t + s - i
        self._yaz([
            "[b]DONEM:[/b] %s -> %s" % (bas, bit), "",
            "Isletme sayisi: [b]%d[/b]" % n,
            "Toplam verilen kart: [b]%d[/b]" % kart,
            "Potansiyel ciro: [b]%.2f %s[/b]" % (pot, PARA), "",
            "Tahsilat: [color=2A9D8F]%.2f[/color]" % t,
            "Satis: [color=2A9D8F]%.2f[/color]" % s,
            "Iade: [color=E63946]%.2f[/color]" % i,
            "[b]Net: %.2f %s[/b]" % (net, PARA),
        ])

    def dokum(self, *a):
        bas, bit = self.bas.text.strip(), self.bit.text.strip()
        con = baglan()
        kayitlar = con.execute(
            "SELECT i.tarih, i.islem_turu, i.tutar, i.adet, i.aciklama, s.isletme_adi"
            " FROM islemler i JOIN isletmeler s ON s.id=i.isletme_id"
            " WHERE i.tarih BETWEEN ? AND ? ORDER BY i.tarih DESC, i.id DESC",
            (bas, bit)
        ).fetchall()
        con.close()
        if not kayitlar:
            self._yaz(["Bu aralikta islem yok."])
            return
        satirlar = ["[b]DOKUM (%s -> %s)[/b]" % (bas, bit), ""]
        for k in kayitlar:
            satirlar.append("%s | %s | %.2f %s | adet:%d | %s | %s" %
                            (k[0], k[1].upper(), k[2], PARA, k[3], k[5], k[4] or ""))
        self._yaz(satirlar)

    def borclular(self, *a):
        con = baglan()
        kayitlar = con.execute(
            "SELECT s.id, s.isletme_adi, s.telefon,"
            " COALESCE(s.kart_adedi*s.birim_fiyat,0),"
            " COALESCE((SELECT SUM(tutar) FROM islemler"
            "  WHERE isletme_id=s.id AND islem_turu='tahsilat'),0)"
            " FROM isletmeler s ORDER BY 4 DESC"
        ).fetchall()
        con.close()
        satirlar = ["[b]BORC DURUMU[/b]", ""]
        for k in kayitlar:
            kalan = k[3] - k[4]
            renk = "E63946" if kalan > 0 else "2A9D8F"
            satirlar.append(
                "[b]%s[/b] (#%d) - %s\n   Borc: %.2f | Odenen: %.2f |"
                " [color=%s]Kalan: %.2f %s[/color]\n" %
                (k[1], k[0], k[2] or "-", k[3], k[4], renk, kalan, PARA)
            )
        self._yaz(satirlar)

    def stok_deger(self, *a):
        con = baglan()
        kayitlar = con.execute(
            "SELECT id, parti_adi, adet_kalan, alis_fiyat, satis_fiyat"
            " FROM partiler ORDER BY id DESC"
        ).fetchall()
        con.close()
        satirlar = ["[b]STOK DEGERI[/b]", ""]
        top_a = 0
        top_s = 0
        for k in kayitlar:
            a = k[2] * k[3]
            s = k[2] * k[4]
            top_a += a
            top_s += s
            satirlar.append("#%d %s - Kalan: %d | Alis: %.2f | Satis: %.2f" %
                            (k[0], k[1], k[2], a, s))
        satirlar.append("")
        satirlar.append("[b]Toplam alis degeri: %.2f %s[/b]" % (top_a, PARA))
        satirlar.append("[b]Toplam satis degeri: %.2f %s[/b]" % (top_s, PARA))
        satirlar.append("[b]Beklenen kar: %.2f %s[/b]" % (top_s - top_a, PARA))
        self._yaz(satirlar)


# =========================================================
# DISA AKTARMA
# =========================================================
class DisaAktarPaneli(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.add_widget(Label(text="[b]EXCEL / CSV DISA AKTAR[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        self.add_widget(Label(text="Tum veriler UTF-8 (Excel uyumlu) CSV olarak yazilir.",
                              color=RENK_KOYU, size_hint_y=None, height=dp(30)))

        bar = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(8))
        b1 = Button(text="Tumunu Aktar", background_color=RENK_YESIL)
        b1.bind(on_release=self.tumunu_aktar)
        b2 = Button(text="Klasoru Goster", background_color=RENK_ORTA)
        b2.bind(on_release=self.klasor_goster)
        bar.add_widget(b1)
        bar.add_widget(b2)
        self.add_widget(bar)

        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)

    def _csv_yaz(self, dosya, basliklar, satirlar):
        with open(dosya, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(basliklar)
            for s in satirlar:
                w.writerow(s)

    def tumunu_aktar(self, *a):
        klasor = os.path.join(KLASOR, DISARI_KLASOR)
        os.makedirs(klasor, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        olusan = []

        con = baglan()
        c = con.cursor()

        s = c.execute(
            "SELECT id, isletme_adi, yetkili_kisi, telefon, adres, kart_seri_no,"
            " kart_adedi, birim_fiyat, kayit_tarihi, son_guncelleme, notlar, aktif"
            " FROM isletmeler"
        ).fetchall()
        d = os.path.join(klasor, "isletmeler_%s.csv" % ts)
        self._csv_yaz(d, ["ID", "Isletme", "Yetkili", "Telefon", "Adres",
                          "Kart Seri No", "Kart Adedi", "Birim Fiyat",
                          "Kayit", "Son Guncelleme", "Notlar", "Aktif"], s)
        olusan.append(d)

        s = c.execute(
            "SELECT i.id, s.isletme_adi, i.islem_turu, i.tutar, i.adet,"
            " i.tarih, i.aciklama FROM islemler i"
            " LEFT JOIN isletmeler s ON s.id=i.isletme_id ORDER BY i.id"
        ).fetchall()
        d = os.path.join(klasor, "islemler_%s.csv" % ts)
        self._csv_yaz(d, ["ID", "Isletme", "Tur", "Tutar", "Adet", "Tarih", "Aciklama"], s)
        olusan.append(d)

        s = c.execute(
            "SELECT id, parti_adi, alis_tarihi, adet_giris, adet_kalan, alis_fiyat,"
            " satis_fiyat, tedarikci, notlar FROM partiler"
        ).fetchall()
        d = os.path.join(klasor, "partiler_%s.csv" % ts)
        self._csv_yaz(d, ["ID", "Parti", "Alis Tarihi", "Giris", "Kalan",
                          "Alis Fiyat", "Satis Fiyat", "Tedarikci", "Notlar"], s)
        olusan.append(d)

        s = c.execute(
            "SELECT h.id, p.parti_adi, h.hareket, h.adet, h.birim_fiyat,"
            " s.isletme_adi, h.tarih, h.aciklama FROM stok_hareketleri h"
            " LEFT JOIN partiler p ON p.id=h.parti_id"
            " LEFT JOIN isletmeler s ON s.id=h.isletme_id ORDER BY h.id"
        ).fetchall()
        d = os.path.join(klasor, "stok_hareketleri_%s.csv" % ts)
        self._csv_yaz(d, ["ID", "Parti", "Hareket", "Adet", "Birim Fiyat",
                          "Isletme", "Tarih", "Aciklama"], s)
        olusan.append(d)

        s = c.execute(
            "SELECT s.isletme_adi, s.telefon,"
            " COALESCE(s.kart_adedi*s.birim_fiyat,0),"
            " COALESCE((SELECT SUM(tutar) FROM islemler"
            "  WHERE isletme_id=s.id AND islem_turu='tahsilat'),0)"
            " FROM isletmeler s"
        ).fetchall()
        borc_satirlar = [(k[0], k[1], "%.2f" % k[2], "%.2f" % k[3], "%.2f" % (k[2] - k[3]))
                         for k in s]
        d = os.path.join(klasor, "borc_durumu_%s.csv" % ts)
        self._csv_yaz(d, ["Isletme", "Telefon", "Borc", "Odenen", "Kalan"], borc_satirlar)
        olusan.append(d)

        con.close()

        self.ic.clear_widgets()
        self.ic.add_widget(Label(text="[b]%d dosya olusturuldu:[/b]" % len(olusan),
                                 markup=True, color=RENK_YESIL,
                                 size_hint_y=None, height=dp(30)))
        for d in olusan:
            self.ic.add_widget(Label(text=os.path.basename(d), color=RENK_KOYU,
                                     size_hint_y=None, height=dp(30)))
        popup_bilgi("Basarili", "%d CSV dosyasi olusturuldu.\n\nKlasor:\n%s"
                    % (len(olusan), klasor))

    def klasor_goster(self, *a):
        klasor = os.path.join(KLASOR, DISARI_KLASOR)
        os.makedirs(klasor, exist_ok=True)
        popup_bilgi("Klasor", klasor)


# =========================================================
# YEDEK PANELI
# =========================================================
class YedekPaneli(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.add_widget(Label(text="[b]YEDEKLEME[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        b1 = Button(text="Yedek Al", size_hint_y=None, height=dp(50),
                    background_color=RENK_YESIL)
        b1.bind(on_release=self.yedek_al)
        self.add_widget(b1)
        b2 = Button(text="Yedekleri Listele", size_hint_y=None, height=dp(50),
                    background_color=RENK_ORTA)
        b2.bind(on_release=self.listele)
        self.add_widget(b2)
        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)

    def yedek_al(self, *a):
        klasor = os.path.join(KLASOR, YEDEK_KLASOR)
        os.makedirs(klasor, exist_ok=True)
        hedef = os.path.join(klasor, "yedek_%s.db" % datetime.now().strftime("%Y%m%d_%H%M%S"))
        try:
            shutil.copy2(db_yolu(), hedef)
            popup_bilgi("Basarili", "Yedek alindi:\n%s" % hedef)
        except Exception as e:
            popup_bilgi("Hata", str(e))

    def listele(self, *a):
        self.ic.clear_widgets()
        klasor = os.path.join(KLASOR, YEDEK_KLASOR)
        if not os.path.isdir(klasor):
            self.ic.add_widget(Label(text="Yedek yok.", color=RENK_VURGU,
                                     size_hint_y=None, height=dp(30)))
            return
        dosyalar = sorted(os.listdir(klasor), reverse=True)
        if not dosyalar:
            self.ic.add_widget(Label(text="Yedek yok.", color=RENK_VURGU,
                                     size_hint_y=None, height=dp(30)))
            return
        for d in dosyalar:
            yol = os.path.join(klasor, d)
            try:
                boyut = os.path.getsize(yol) / 1024.0
            except OSError:
                boyut = 0
            self.ic.add_widget(Label(text="%s  (%.1f KB)" % (d, boyut),
                                     color=RENK_KOYU, size_hint_y=None, height=dp(35)))


# =========================================================
# KULLANICI PANELI
# =========================================================
class KullaniciPaneli(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.add_widget(Label(text="[b]KULLANICI YONETIMI[/b]", markup=True,
                              font_size="20sp", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))

        form = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        form.add_widget(Label(text="Kullanici Adi", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        self.kadi = TextInput(multiline=False, size_hint_y=None, height=dp(40))
        form.add_widget(self.kadi)
        form.add_widget(Label(text="Sifre", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        self.sifre = TextInput(password=True, multiline=False,
                               size_hint_y=None, height=dp(40))
        form.add_widget(self.sifre)
        form.add_widget(Label(text="Rol", color=RENK_KOYU,
                              size_hint_y=None, height=dp(40)))
        self.rol = Spinner(text="personel", values=("personel", "yonetici"),
                           size_hint_y=None, height=dp(40))
        form.add_widget(self.rol)
        self.add_widget(form)

        b = Button(text="Kullanici Ekle", size_hint_y=None, height=dp(50),
                   background_color=RENK_YESIL)
        b.bind(on_release=self.ekle)
        self.add_widget(b)

        self.scroll = ScrollView()
        self.ic = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.ic.bind(minimum_height=self.ic.setter("height"))
        self.scroll.add_widget(self.ic)
        self.add_widget(self.scroll)
        self.listele()

    def ekle(self, *a):
        kad = self.kadi.text.strip()
        sf = self.sifre.text
        if not kad or len(sf) < 4:
            popup_bilgi("Hata", "Kullanici adi ve en az 4 karakter sifre gerekli.")
            return
        try:
            kullanici_ekle(kad, sf, self.rol.text)
        except sqlite3.IntegrityError:
            popup_bilgi("Hata", "Bu kullanici zaten var.")
            return
        self.kadi.text = ""
        self.sifre.text = ""
        self.listele()
        popup_bilgi("Basarili", "Kullanici eklendi.")

    def listele(self):
        self.ic.clear_widgets()
        for k in tum_kullanicilar():
            satir = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
            satir.add_widget(Label(text="#%d %s (%s) - %s" % (k[0], k[1], k[2], k[3]),
                                   color=RENK_KOYU, size_hint_x=0.75))
            b = Button(text="Sil", size_hint_x=0.25, background_color=RENK_VURGU)
            b.bind(on_release=lambda *a, kid=k[0]: self.sil(kid))
            satir.add_widget(b)
            self.ic.add_widget(satir)

    def sil(self, kid):
        def _o():
            ok, msg = kullanici_sil(kid)
            if ok:
                self.listele()
            popup_bilgi("Bilgi", msg)
        popup_onay("Emin misiniz?", "Kullanici silinecek.", _o)


# =========================================================
# DETAY PENCERESI
# =========================================================
class DetayPenceresi(BoxLayout):
    def __init__(self, isletme_id, yenile_cb=None, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.isletme_id = isletme_id
        self.yenile_cb = yenile_cb

        self.icerik = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.icerik.bind(minimum_height=self.icerik.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.icerik)
        self.add_widget(sv)

        bar = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        for t, cb, rk in [("Duzenle", self.duzenle, RENK_ORTA),
                          ("PDF Fis", self.pdf_fis, RENK_YESIL),
                          ("Aktif/Pasif", self.aktif_degistir, RENK_SARI),
                          ("Sil", self.sil, RENK_VURGU),
                          ("Kapat", lambda *a: self._popup.dismiss(), RENK_KOYU)]:
            b = Button(text=t, background_color=rk)
            b.bind(on_release=cb)
            bar.add_widget(b)
        self.add_widget(bar)
        self._popup = None
        self.yukle()

    def yukle(self):
        self.icerik.clear_widgets()
        con = baglan()
        k = con.execute("SELECT * FROM isletmeler WHERE id=?", (self.isletme_id,)).fetchone()
        islemler = con.execute(
            "SELECT tarih, islem_turu, tutar, adet, aciklama FROM islemler"
            " WHERE isletme_id=? ORDER BY tarih DESC", (self.isletme_id,)
        ).fetchall()
        con.close()
        if not k:
            self.icerik.add_widget(Label(text="Kayit bulunamadi."))
            return
        bilgi = ("[b]%s[/b]\nYetkili: %s\nTelefon: %s\nAdres: %s\n"
                 "Kart Seri No: %s\nKart Adedi: %d\nBirim Fiyat: %s %s\n"
                 "Toplam Bedel: %.2f %s\nKayit: %s\nSon Guncelleme: %s\n"
                 "Aktif: %s\nNot: %s\n" %
                 (k[1], k[2] or "-", k[3] or "-", k[4] or "-", k[5] or "-",
                  k[6] or 0, k[7] or 0, PARA, kart_tutar(k[6], k[7]), PARA,
                  k[8] or "-", k[9] or "-",
                  "Evet" if k[11] else "Hayir", k[10] or "-"))
        lbl = Label(text=bilgi, markup=True, halign="left", valign="top",
                    color=RENK_KOYU, size_hint_y=None)
        lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        lbl.bind(texture_size=lambda i, ts: setattr(i, "height", ts[1] + dp(10)))
        self.icerik.add_widget(lbl)

        self.icerik.add_widget(Label(text="[b]Islem Gecmisi[/b]", markup=True,
                                     color=RENK_KOYU, size_hint_y=None, height=dp(30)))
        if not islemler:
            self.icerik.add_widget(Label(text="Islem yok.", color=RENK_VURGU,
                                         size_hint_y=None, height=dp(30)))
        else:
            for i in islemler:
                self.icerik.add_widget(Label(
                    text="%s | %s | %.2f %s | adet:%d | %s" %
                         (i[0], i[1], i[2] or 0, PARA, i[3] or 0, i[4] or ""),
                    color=RENK_KOYU, size_hint_y=None, height=dp(30)))

    def duzenle(self, *a):
        con = baglan()
        k = con.execute("SELECT * FROM isletmeler WHERE id=?", (self.isletme_id,)).fetchone()
        con.close()
        if not k:
            return
        app = App.get_running_app()
        ana = app.root.get_screen("ana")
        ana.form.doldur(k)
        ana.sekme_sec(0)
        self._popup.dismiss()

    def pdf_fis(self, *a):
        try:
            from reportlab.lib.pagesizes import A5
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
        except ImportError:
            popup_bilgi("Eksik", "reportlab kurulu degil.")
            return
        con = baglan()
        k = con.execute("SELECT * FROM isletmeler WHERE id=?", (self.isletme_id,)).fetchone()
        islemler = con.execute(
            "SELECT tarih, islem_turu, tutar, aciklama FROM islemler"
            " WHERE isletme_id=? ORDER BY tarih", (self.isletme_id,)
        ).fetchall()
        con.close()
        dosya = os.path.join(KLASOR, "fis_%d_%s.pdf" %
                             (self.isletme_id, datetime.now().strftime("%Y%m%d_%H%M%S")))
        c = canvas.Canvas(dosya, pagesize=A5)
        gen, yuk = A5
        y = yuk - 20 * mm
        c.setFont("Helvetica-Bold", 16)
        c.drawString(15 * mm, y, "NFC KART MALATYA")
        y -= 8 * mm
        c.setFont("Helvetica", 10)
        c.drawString(15 * mm, y, "Kart Teslim ve Tahsilat Fisi")
        c.line(15 * mm, y - 2 * mm, gen - 15 * mm, y - 2 * mm)
        y -= 12 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(15 * mm, y, "Isletme: %s" % (k[1] or ""))
        y -= 6 * mm
        c.setFont("Helvetica", 10)
        for e, d in [("Yetkili", k[2] or "-"), ("Telefon", k[3] or "-"),
                     ("Adres", k[4] or "-"), ("Kart Seri No", k[5] or "-"),
                     ("Kart Adedi", str(k[6] or 0)),
                     ("Birim Fiyat", "%s TL" % (k[7] or 0)),
                     ("Toplam", "%.2f TL" % kart_tutar(k[6], k[7])),
                     ("Kayit", k[8] or "-")]:
            c.drawString(15 * mm, y, "%s: %s" % (e, d))
            y -= 5 * mm
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(15 * mm, y, "Islem Gecmisi")
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        for i in islemler:
            if y < 25 * mm:
                c.showPage()
                y = yuk - 20 * mm
                c.setFont("Helvetica", 9)
            c.drawString(15 * mm, y, "%s | %s | %.2f TL | %s" %
                         (i[0], i[1], i[2] or 0, i[3] or ""))
            y -= 5 * mm
        y -= 8 * mm
        c.drawString(15 * mm, y, "Yetkili Imza: ______________________")
        y -= 8 * mm
        c.drawString(15 * mm, y, "Musteri Imza: ______________________")
        c.showPage()
        c.save()
        popup_bilgi("PDF", "Olusturuldu:\n%s" % dosya)

    def aktif_degistir(self, *a):
        con = baglan()
        k = con.execute("SELECT aktif FROM isletmeler WHERE id=?", (self.isletme_id,)).fetchone()
        yeni = 0 if (k and k[0]) else 1
        con.execute("UPDATE isletmeler SET aktif=?, son_guncelleme=? WHERE id=?",
                    (yeni, simdi(), self.isletme_id))
        con.commit()
        con.close()
        self.yukle()
        if self.yenile_cb:
            self.yenile_cb()

    def sil(self, *a):
        def _o():
            con = baglan()
            con.execute("DELETE FROM isletmeler WHERE id=?", (self.isletme_id,))
            con.commit()
            con.close()
            if self.yenile_cb:
                self.yenile_cb()
            self._popup.dismiss()
            popup_bilgi("Silindi", "Kayit silindi.")
        popup_onay("Emin misiniz?", "Isletme ve tum islemleri silinecek.", _o)


# =========================================================
# APP
# =========================================================
class NFCMalatyaApp(App):
    aktif_kullanici = None

    def build(self):
        global KLASOR
        self.title = APP_ADI
        # Android'de uygulama paketinin kurulu oldugu klasor yazilabilir degildir.
        # Veritabani, ayarlar, yedekler ve ciktilari uygulamanin guvenli veri klasorune yaz.
        KLASOR = self.user_data_dir
        os.makedirs(KLASOR, exist_ok=True)
        os.makedirs(os.path.join(KLASOR, YEDEK_KLASOR), exist_ok=True)
        os.makedirs(os.path.join(KLASOR, DISARI_KLASOR), exist_ok=True)
        tablolari_kur()

        sm = ScreenManager()
        sm.add_widget(GirisEkrani(name="giris"))
        sm.add_widget(AnaEkran(name="ana"))

        a = ayar_oku()
        if a.get("beni_hatirla") and a.get("son_kullanici"):
            k = kullanici_bul(a["son_kullanici"])
            if k:
                self.aktif_kullanici = {"id": k[0], "kadi": k[1], "rol": k[4]}
                sm.current = "ana"
                Clock.schedule_once(
                    lambda dt: sm.get_screen("ana").yenile(), 0.4
                )
                return sm

        sm.current = "giris"
        return sm


if __name__ == "__main__":
    NFCMalatyaApp().run()