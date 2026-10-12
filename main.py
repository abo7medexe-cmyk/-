# -*- coding: utf-8 -*-
import threading
import json
import urllib.request
import urllib.parse
import os
import re
from datetime import datetime

import arabic_reshaper

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Rectangle

FONT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "NotoNaskhArabic-VariableFont_wght.ttf"
)

if os.path.exists(FONT_FILE):
    LabelBase.register(name="Arabic", fn_regular=FONT_FILE)
    FONT = "Arabic"
else:
    FONT = "Roboto"


def arabic_text(text):
    """
    حل تجريبي دون python-bidi:
    يشكّل الحروف عبر arabic_reshaper ثم يعكس ترتيب الكلمات والحروف العربية.
    أبقِ الأرقام/الكلمات اللاتينية داخل كل كلمة كما هي قدر الإمكان.
    """
    text = str(text)
    try:
        shaped = arabic_reshaper.reshape(text)
    except Exception:
        return text

    # افصل النص إلى كلمات مع الاحتفاظ بالمسافات.
    parts = re.split(r'(\s+)', shaped)
    # نعكس ترتيب الكلمات فقط، ونقلب حروف الكلمات العربية.
    words = [p for p in parts if p and not p.isspace()]
    spaces = [p for p in parts if p and p.isspace()]
    if not words:
        return shaped

    def is_arabic_word(word):
        return any('\u0600' <= ch <= '\u06FF' or '\uFB50' <= ch <= '\uFEFF'
                   for ch in word)

    visual_words = []
    for word in reversed(words):
        if is_arabic_word(word):
            # إبقاء الأرقام اللاتينية/الأوقات غير معكوسة داخل الكلمة
            chunks = re.findall(r'[\u0600-\u06FF\uFB50-\uFEFF]+|[A-Za-z0-9:.+-]+|.', word)
            visual_words.append(''.join(
                chunk[::-1] if any('\u0600' <= c <= '\u06FF' or '\uFB50' <= c <= '\uFEFF'
                                   for c in chunk) else chunk
                for chunk in reversed(chunks)
            ))
        else:
            visual_words.append(word)
    # هذا مناسب غالبًا للنصوص العربية القصيرة، وليس بديلًا كاملًا لخوارزمية Unicode BiDi.
    return ' '.join(visual_words)


PRAYERS = [
    ("الفجر", "Fajr"),
    ("الشروق", "Sunrise"),
    ("الظهر", "Dhuhr"),
    ("العصر", "Asr"),
    ("المغرب", "Maghrib"),
    ("العشاء", "Isha"),
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AdhanAlarm/1.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def get_ip_location():
    data = fetch_json("https://ipapi.co/json/")
    lat, lon = data.get("latitude"), data.get("longitude")
    city = data.get("city") or data.get("country_name") or "موقع تقريبي"
    if lat is None or lon is None:
        raise ValueError("تعذر تحديد الموقع")
    return float(lat), float(lon), city


def get_prayer_times(lat, lon):
    today = datetime.now().strftime("%d-%m-%Y")
    params = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "method": 3})
    payload = fetch_json(f"https://api.aladhan.com/v1/timings/{today}?{params}")
    if payload.get("code") != 200:
        raise ValueError("تعذر جلب مواقيت الصلاة")
    return payload["data"]["timings"], payload["data"]["date"]["readable"]


class AdhanApp(App):
    def build(self):
        self.title = "منبّه الأذان"
        self.lat = None
        self.lon = None

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        with root.canvas.before:
            Color(*get_color_from_hex("#0B2E2B"))
            self.background = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self.update_bg, size=self.update_bg)

        root.add_widget(Label(
            text=arabic_text("منبّه الأذان"), font_name=FONT, font_size="28sp",
            bold=True, color=get_color_from_hex("#F5D77A"),
            size_hint_y=None, height=dp(55)
        ))

        self.location_label = Label(
            text=arabic_text("جارٍ تحديد الموقع..."), font_name=FONT,
            font_size="16sp", color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(55), halign="center"
        )
        root.add_widget(self.location_label)

        controls = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.lat_input = TextInput(hint_text="خط العرض", multiline=False,
                                   input_filter="float", font_size="16sp")
        self.lon_input = TextInput(hint_text="خط الطول", multiline=False,
                                   input_filter="float", font_size="16sp")
        controls.add_widget(self.lat_input)
        controls.add_widget(self.lon_input)
        root.add_widget(controls)

        refresh = Button(
            text=arabic_text("تحديث مواقيت الصلاة"), font_name=FONT, font_size="18sp",
            size_hint_y=None, height=dp(50), background_normal="",
            background_color=get_color_from_hex("#D9B95B"),
            color=get_color_from_hex("#102E2A")
        )
        refresh.bind(on_release=self.manual_refresh)
        root.add_widget(refresh)

        self.date_label = Label(
            text=arabic_text("مواقيت اليوم"), font_name=FONT, font_size="19sp",
            color=get_color_from_hex("#F5D77A"), size_hint_y=None, height=dp(40)
        )
        root.add_widget(self.date_label)

        scroll = ScrollView()
        self.rows = BoxLayout(orientation="vertical", spacing=dp(9), size_hint_y=None)
        self.rows.bind(minimum_height=self.rows.setter("height"))
        scroll.add_widget(self.rows)
        root.add_widget(scroll)

        self.status = Label(
            text=arabic_text("المواقيت تحتاج إلى اتصال بالإنترنت"),
            font_name=FONT, font_size="13sp", color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(48), halign="center"
        )
        root.add_widget(self.status)

        threading.Thread(target=self.initial_location, daemon=True).start()
        return root

    def update_bg(self, widget, *_):
        self.background.pos = widget.pos
        self.background.size = widget.size

    def initial_location(self):
        try:
            lat, lon, city = get_ip_location()
            Clock.schedule_once(lambda dt: self.set_location(lat, lon, city))
            self.load_times(lat, lon)
        except Exception:
            Clock.schedule_once(lambda dt: self.show_error(
                "تعذر تحديد الموقع. أدخل الإحداثيات يدويًا."
            ))

    def set_location(self, lat, lon, city):
        self.lat, self.lon = lat, lon
        self.lat_input.text = str(lat)
        self.lon_input.text = str(lon)
        self.location_label.text = arabic_text(
            f"الموقع التقريبي: {city} ({lat:.4f}, {lon:.4f})"
        )

    def manual_refresh(self, *_):
        try:
            lat = float(self.lat_input.text.strip())
            lon = float(self.lon_input.text.strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            self.lat, self.lon = lat, lon
            threading.Thread(target=self.load_times, args=(lat, lon), daemon=True).start()
            self.status.text = arabic_text("جارٍ جلب المواقيت...")
        except Exception:
            self.status.text = arabic_text("تحقق من خط العرض والطول")

    def load_times(self, lat, lon):
        try:
            timings, date_text = get_prayer_times(lat, lon)
            Clock.schedule_once(lambda dt: self.display_times(timings, date_text))
        except Exception:
            Clock.schedule_once(lambda dt: self.show_error(
                "تعذر جلب المواقيت. تحقق من الإنترنت."
            ))

    def display_times(self, timings, date_text):
        self.rows.clear_widgets()
        self.date_label.text = arabic_text(f"مواقيت الصلاة - {date_text}")

        for arabic, key in PRAYERS:
            value = timings.get(key, "--:--").split(" ")[0]
            row = BoxLayout(size_hint_y=None, height=dp(58),
                            padding=dp(12), spacing=dp(10))
            with row.canvas.before:
                Color(*get_color_from_hex("#16443D"))
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(12)])
            row.bind(pos=lambda w, p, shape=bg: setattr(shape, "pos", p),
                     size=lambda w, s, shape=bg: setattr(shape, "size", s))

            row.add_widget(Label(
                text=arabic_text(arabic), font_name=FONT, font_size="20sp",
                color=(1, 1, 1, 1), halign="right"
            ))
            row.add_widget(Label(
                text=value, font_size="21sp", bold=True,
                color=get_color_from_hex("#F5D77A"), size_hint_x=0.4
            ))
            self.rows.add_widget(row)

        self.status.text = arabic_text(
            "تم تحديث المواقيت. التنبيه بالخلفية غير مفعّل بعد."
        )

    def show_error(self, message):
        self.status.text = arabic_text(message)


if __name__ == "__main__":
    AdhanApp().run()
