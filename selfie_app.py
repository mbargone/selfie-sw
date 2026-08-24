#!/usr/bin/env python3
"""
Selfie App - Raspberry Pi Edition
Application locale qui combine les 3 styles: Polaroid, Realiste, Cartoon
Optimisee pour ecran 1024x600
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import base64
import json
import urllib.request
import urllib.error
import threading
import os
import io
from datetime import datetime
import time
import qrcode

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

# Chemin des images personnages
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_DIR = os.path.join(SCRIPT_DIR, "personnages")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

CHARACTERS = [
    {"name": "Ambroise", "file": "ambroise.png"},
    {"name": "Cedric", "file": "cedric.png"},
    {"name": "Fe", "file": "fe.png"},
    {"name": "Nika", "file": "nika.png"},
    {"name": "Samuel", "file": "Samuel.png"},
    {"name": "Emilie", "file": "emilie.png"},
    {"name": "Michel (auteur)", "file": "michel-toxedo.png"},
]

PROMPTS = {
    "realiste": (
        "I have two photos. "
        "Photo 1 is a character named {name} from the book Particule du Diable. "
        "Photo 2 is a visitor at a book launch event. "
        "Create a single photorealistic image showing both people standing side by side on a glamorous red carpet. "
        "SCALE: Both people must be the SAME height and scale in the final image - match the visitor's size to the character's size from Photo 1. "
        "FACE: Preserve EXACTLY the visitor's face, facial features, hair color, hairstyle, glasses, beard, and skin tone from Photo 2. Do NOT alter the face or hair in any way. "
        "OUTFIT: Dress the visitor in elegant evening wear appropriate for a glamorous book launch gala: "
        "if the visitor appears to be a man, dress them in a classic black tuxedo with white shirt and bow tie; "
        "if the visitor appears to be a woman, dress them in an elegant evening gown. "
        "Preserve EXACTLY the character appearance from Photo 1. "
        "Both people should be smiling and looking at the camera. "
        "Background: luxurious red carpet with velvet ropes, golden stanchions, and soft event lighting. "
        "Style: professional event photography, sharp and well-lit. "
        "The visitor is on the left, the character is on the right."
    ),
    "cartoon": (
        "I have two photos. "
        "Photo 1 is a character named {name} from a book. "
        "Photo 2 is a real person (a visitor). "
        "Create a single image ENTIRELY in Pixar/Disney 3D animation style. EVERYTHING must be in this style - the people, the background, the objects, the lighting. Nothing should look photorealistic. "
        "SCENE: The character (from Photo 1) is holding a phone up in the air with one arm extended, taking a selfie with the visitor (from Photo 2). They are standing close together on a glamorous red carpet. The character's arm and phone are visible in the upper part of the image. "
        "VISITOR (from Photo 2): Convert into Pixar 3D style but FAITHFULLY preserve their identity. CRITICAL features to match exactly: hair color, hairstyle, hair length, baldness pattern, facial hair (beard, mustache, goatee - exact shape and color), glasses (exact frame style and color), skin tone, eye color, and clothing. The person MUST immediately recognize themselves. Make them look flattering - slim the body slightly, confident posture - but the face and hair must be a faithful cartoon portrait of the real person. Do NOT change hair color, do NOT remove glasses, do NOT alter facial hair. "
        "CHARACTER (from Photo 1): Convert into the same Pixar 3D style while keeping their recognizable features and clothing. They are the one holding the phone for the selfie. "
        "SCALE: Both people are the same height, standing side by side. "
        "BACKGROUND: Glamorous red carpet event with velvet ropes, golden stanchions, paparazzi, and warm event lighting - ALL rendered in Pixar 3D animated style. "
        "Both people are smiling and looking toward the phone camera. The visitor is on the left, the character holding the phone is on the right. "
        "STYLE: HEAVILY stylized Pixar 3D animation. Exaggerated cartoon proportions - bigger heads, bigger eyes, rounder faces, smaller bodies. Smooth plastic-like skin with NO pores or texture. Very saturated vibrant colors. Strong rim lighting. Thick eyebrows, big smiles. Like characters from Inside Out or Up. Push the cartoon look as far as possible while keeping people recognizable. ZERO photorealism."
    ),
    "polaroid": None
}

class SelfieApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Selfie - Particule du Diable")
        self.root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)

        self.current_character_index = 0
        self.selected_style = tk.StringVar(value="cartoon")
        self.captured_photo = None
        self.camera = None
        self.camera_active = False
        self.result_image = None

        self.character_images = []
        self.character_thumbnails = []
        self.load_characters()

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self.build_ui()

        self.root.bind("<Left>", lambda e: self.prev_character())
        self.root.bind("<Right>", lambda e: self.next_character())
        self.root.bind("<Escape>", lambda e: self.root.quit())
        self.root.bind("p", lambda e: self.select_style("polaroid"))
        self.root.bind("P", lambda e: self.select_style("polaroid"))
        self.root.bind("r", lambda e: self.select_style("realiste"))
        self.root.bind("R", lambda e: self.select_style("realiste"))
        self.root.bind("c", lambda e: self.select_style("cartoon"))
        self.root.bind("C", lambda e: self.select_style("cartoon"))
        self.root.bind("<Return>", self.handle_enter_key)

    def load_characters(self):
        for char in CHARACTERS:
            path = os.path.join(CHARACTERS_DIR, char["file"])
            if os.path.exists(path):
                img = Image.open(path)
                self.character_images.append(img)
                thumb = img.copy()
                thumb.thumbnail((300, 420), Image.LANCZOS)
                self.character_thumbnails.append(ImageTk.PhotoImage(thumb))
            else:
                img = Image.new("RGB", (300, 420), "#333333")
                draw = ImageDraw.Draw(img)
                draw.text((50, 170), char["name"], fill="white")
                self.character_images.append(img)
                self.character_thumbnails.append(ImageTk.PhotoImage(img))

    def build_ui(self):
        self.main_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(self.main_frame, text="Selfie avec les Personnages",
                         font=("Arial", 20, "bold"), fg="#FFD700", bg="#1a1a2e")
        title.pack(pady=(10, 5))

        self.center_frame = tk.Frame(self.main_frame, bg="#1a1a2e")
        self.center_frame.pack(fill=tk.BOTH, expand=True)

        self.step1_frame = tk.Frame(self.center_frame, bg="#1a1a2e")
        self.step2_frame = tk.Frame(self.center_frame, bg="#1a1a2e")
        self.step3_frame = tk.Frame(self.center_frame, bg="#1a1a2e")
        self.step4_frame = tk.Frame(self.center_frame, bg="#1a1a2e")

        self.build_step1()
        self.build_step2()
        self.build_step3()
        self.build_step4()
        self.show_step(1)

    def build_step1(self):
        left_frame = tk.Frame(self.step1_frame, bg="#1a1a2e")
        left_frame.pack(side=tk.LEFT, padx=(20, 5), pady=10, expand=True)

        right_frame = tk.Frame(self.step1_frame, bg="#1a1a2e")
        right_frame.pack(side=tk.RIGHT, padx=(5, 10), pady=10)

        nav_frame = tk.Frame(left_frame, bg="#1a1a2e")
        nav_frame.pack()

        self.btn_prev = tk.Button(nav_frame, text="\u25C0", font=("Arial", 32, "bold"),
                                  command=self.prev_character, bg="#4a90e2", fg="white",
                                  relief=tk.FLAT, width=3, height=2, cursor="hand2")
        self.btn_prev.pack(side=tk.LEFT, padx=5)

        self.character_label = tk.Label(nav_frame, bg="#1a1a2e")
        self.character_label.pack(side=tk.LEFT, padx=10)

        self.btn_next = tk.Button(nav_frame, text="\u25B6", font=("Arial", 32, "bold"),
                                  command=self.next_character, bg="#4a90e2", fg="white",
                                  relief=tk.FLAT, width=3, height=2, cursor="hand2")
        self.btn_next.pack(side=tk.LEFT, padx=5)

        self.char_name_label = tk.Label(left_frame, text="", font=("Arial", 16, "bold"),
                                        fg="white", bg="#1a1a2e")
        self.char_name_label.pack(pady=(10, 0))

        style_title = tk.Label(right_frame, text="Style du selfie:",
                               font=("Arial", 14, "bold"), fg="white", bg="#1a1a2e")
        style_title.pack(pady=(20, 10))

        self.style_buttons = {}
        styles = [
            ("Polaroid", "polaroid", "#8B4513"),
            ("Realiste", "realiste", "#1a5276"),
            ("Cartoon", "cartoon", "#6c3483"),
        ]

        for text, value, color in styles:
            btn = tk.Button(right_frame, text=text, font=("Arial", 13, "bold"),
                           bg=color, fg="white", relief=tk.RAISED, bd=3,
                           width=16, height=1, cursor="hand2",
                           activebackground=color, activeforeground="#FFD700",
                           command=lambda v=value: self.select_style(v))
            btn.pack(pady=6)
            self.style_buttons[value] = btn

        self.highlight_style_button()

        self.btn_start = tk.Button(right_frame, text="Prendre la photo \u27A1",
                                   font=("Arial", 18, "bold"), bg="#27ae60", fg="white",
                                   command=self.go_to_camera, relief=tk.FLAT,
                                   padx=30, pady=15, cursor="hand2")
        self.btn_start.pack(pady=30)

        self.update_character_display()

    def build_step2(self):
        self.video_label = tk.Label(self.step2_frame, bg="black")
        self.video_label.pack(pady=10)

        btn_frame = tk.Frame(self.step2_frame, bg="#1a1a2e")
        btn_frame.pack(pady=10)

        self.btn_capture = tk.Button(btn_frame, text="Prendre la photo",
                                     font=("Arial", 14, "bold"), bg="#27ae60", fg="white",
                                     command=self.capture_photo, relief=tk.FLAT,
                                     padx=20, pady=10)
        self.btn_capture.pack(side=tk.LEFT, padx=10)

        self.btn_back1 = tk.Button(btn_frame, text="Retour",
                                   font=("Arial", 12), bg="#666", fg="white",
                                   command=lambda: self.show_step(1), relief=tk.FLAT,
                                   padx=15, pady=8)
        self.btn_back1.pack(side=tk.LEFT, padx=10)

    def build_step3(self):
        self.loading_label = tk.Label(self.step3_frame, text="Generation en cours...",
                                      font=("Arial", 18, "bold"), fg="#87ceeb", bg="#1a1a2e")
        self.loading_label.pack(pady=50)

        self.progress_label = tk.Label(self.step3_frame, text="Veuillez patienter (15-30 secondes)",
                                       font=("Arial", 12), fg="#888", bg="#1a1a2e")
        self.progress_label.pack()

    def build_step4(self):
        # Layout horizontal: image a gauche, controles a droite
        content_frame = tk.Frame(self.step4_frame, bg="#1a1a2e")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Image a gauche
        left_frame = tk.Frame(content_frame, bg="#1a1a2e")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.result_label = tk.Label(left_frame, bg="#1a1a2e")
        self.result_label.pack(pady=5)

        # Controles a droite
        right_frame = tk.Frame(content_frame, bg="#1a1a2e", width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 10))
        right_frame.pack_propagate(False)

        self.btn_restart = tk.Button(right_frame, text="Nouveau selfie",
                                     font=("Arial", 14, "bold"), bg="#4a90e2", fg="white",
                                     command=self.restart, relief=tk.FLAT,
                                     width=18, height=2)
        self.btn_restart.pack(pady=10)

        # Section QR Code
        qr_frame = tk.Frame(right_frame, bg="#2a2a4e", relief=tk.RIDGE, bd=1)
        qr_frame.pack(pady=(20, 0), fill=tk.X, padx=5)

        qr_title = tk.Label(qr_frame, text="Scanne pour obtenir\nton selfie!",
                             font=("Arial", 11, "bold"), fg="#87ceeb", bg="#2a2a4e")
        qr_title.pack(pady=(8, 5))

        self.qr_label = tk.Label(qr_frame, bg="#2a2a4e")
        self.qr_label.pack(padx=10, pady=10)

        self.qr_status = tk.Label(qr_frame, text="", font=("Arial", 9),
                                  fg="#888", bg="#2a2a4e")
        self.qr_status.pack(pady=(0, 5))

    def show_step(self, step):
        for frame in [self.step1_frame, self.step2_frame, self.step3_frame, self.step4_frame]:
            frame.pack_forget()

        self.loading_animation_active = False

        if step == 1:
            self.stop_camera()
            self.step1_frame.pack(fill=tk.BOTH, expand=True)
        elif step == 2:
            self.step2_frame.pack(fill=tk.BOTH, expand=True)
            self.start_camera()
        elif step == 3:
            self.stop_camera()
            self.step3_frame.pack(fill=tk.BOTH, expand=True)
            self.loading_animation_active = True
            self.animate_loading()
        elif step == 4:
            self.step4_frame.pack(fill=tk.BOTH, expand=True)

    def animate_loading(self, frame=0):
        """Animation de chargement pendant la generation"""
        if not self.loading_animation_active:
            return
        dots = ["   ", ".  ", ".. ", "..."]
        spinner = ["\u2808", "\u2818", "\u2838", "\u2834", "\u2826", "\u2807", "\u280b", "\u2809"]
        current_spinner = spinner[frame % len(spinner)]
        current_dots = dots[frame % len(dots)]
        self.loading_label.configure(
            text=f"{current_spinner}  Generation en cours{current_dots}  {current_spinner}")
        self.progress_label.configure(
            text=f"Veuillez patienter (15-30 secondes)")
        self.root.after(300, self.animate_loading, frame + 1)

    def select_style(self, style):
        self.selected_style.set(style)
        self.highlight_style_button()

    def highlight_style_button(self):
        colors = {"polaroid": "#8B4513", "realiste": "#1a5276", "cartoon": "#6c3483"}
        for value, btn in self.style_buttons.items():
            if value == self.selected_style.get():
                btn.configure(bg="#FFD700", fg="#1a1a2e", relief=tk.SUNKEN, bd=4)
            else:
                btn.configure(bg=colors[value], fg="white", relief=tk.RAISED, bd=3)

    def update_character_display(self):
        idx = self.current_character_index
        self.character_label.configure(image=self.character_thumbnails[idx])
        self.char_name_label.configure(text=CHARACTERS[idx]["name"])

    def prev_character(self):
        self.current_character_index = (self.current_character_index - 1) % len(CHARACTERS)
        self.update_character_display()

    def next_character(self):
        self.current_character_index = (self.current_character_index + 1) % len(CHARACTERS)
        self.update_character_display()

    def handle_enter_key(self, event):
        """Enter declenche l action selon l etape actuelle"""
        if self.step1_frame.winfo_ismapped():
            self.go_to_camera()
        elif self.step2_frame.winfo_ismapped():
            self.capture_photo()


    def go_to_camera(self):
        self.show_step(2)

    def start_camera(self):
        if not self.camera_active:
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera_active = True
            self.update_camera()

    def stop_camera(self):
        self.camera_active = False
        if self.camera:
            self.camera.release()
            self.camera = None

    def update_camera(self):
        if self.camera_active and self.camera:
            ret, frame = self.camera.read()
            if ret:
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img = img.resize((480, 360), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.video_label.configure(image=photo)
                self.video_label.image = photo
            self.root.after(30, self.update_camera)
    def capture_photo(self):
        if self.camera:
            ret, frame = self.camera.read()
            if ret:
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.captured_photo = Image.fromarray(frame_rgb)
                self.show_step(3)
                threading.Thread(target=self.generate_selfie, daemon=True).start()

    def generate_selfie(self):
        style = self.selected_style.get()
        char_idx = self.current_character_index
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    self.root.after(0, lambda a=attempt: self.loading_label.configure(
                        text=f"Probleme rencontre, nouvel essai ({a}/{max_retries})...",
                        fg="#e67e22"))
                    self.root.after(0, lambda: self.progress_label.configure(
                        text="Veuillez patienter..."))
                    time.sleep(2)

                if style == "polaroid":
                    result = self.generate_polaroid(char_idx)
                else:
                    result = self.generate_with_gemini(char_idx, style)

                self.result_image = result
                self.root.after(0, self.show_result)
                return
            except Exception as e:
                error_msg = str(e)
                print(f"[ERREUR] Tentative {attempt}/{max_retries}: {error_msg}")
                if attempt == max_retries:
                    self.root.after(0, lambda: self.show_error_with_options(error_msg))

    def generate_polaroid(self, char_idx):
        char_img = self.character_images[char_idx].copy()
        user_img = self.captured_photo.copy()

        # Canvas fond tapis rouge
        canvas = Image.new("RGB", (1920, 1080), "#8B0000")
        draw = ImageDraw.Draw(canvas)

        # Taille des photos polaroid (format carre avec bordure blanche)
        photo_size = 630

        # Redimensionner en carre
        char_img = char_img.resize((photo_size, photo_size), Image.LANCZOS)
        user_img = user_img.resize((photo_size, photo_size), Image.LANCZOS)

        # Creer cadre polaroid (bordure blanche epaisse, plus grande en bas)
        border_top = 25
        border_side = 25
        border_bottom = 80
        pol_w = photo_size + border_side * 2
        pol_h = photo_size + border_top + border_bottom

        # Polaroid visiteur (legere rotation gauche)
        user_pol = Image.new("RGBA", (pol_w, pol_h), "white")
        user_pol.paste(user_img, (border_side, border_top))
        user_pol = user_pol.rotate(5, expand=True, fillcolor=(0, 0, 0, 0))

        # Polaroid personnage (legere rotation droite)
        char_pol = Image.new("RGBA", (pol_w, pol_h), "white")
        char_pol.paste(char_img, (border_side, border_top))
        char_pol = char_pol.rotate(-5, expand=True, fillcolor=(0, 0, 0, 0))

        # Placer les polaroids sur le canvas (personnage en dessous, visiteur par-dessus)
        # Centrer verticalement
        center_y = (1080 - pol_h) // 2 - 30
        # Personnage a droite (en dessous)
        canvas.paste(char_pol, (750, center_y), char_pol)
        # Visiteur a gauche, chevauche le personnage
        canvas.paste(user_pol, (450, center_y + 40), user_pol)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((540, 80), "TAPIS ROUGE", fill="#FFD700", font=font, anchor="mt")
        draw.text((540, 140), "Particule du Diable", fill="white", font=font, anchor="mt")

        return canvas

    def generate_with_gemini(self, char_idx, style):
        character = CHARACTERS[char_idx]
        print(f"[GEMINI] Debut - personnage: {character['name']}, style: {style}")

        if not GEMINI_API_KEY or GEMINI_API_KEY == "VOTRE_CLE_API_ICI":
            raise Exception("Cle API Gemini non configuree. Faites: export GEMINI_API_KEY=votre_cle")

        char_img = self.character_images[char_idx]
        char_buffer = io.BytesIO()
        char_img.save(char_buffer, format="PNG")
        char_b64 = base64.b64encode(char_buffer.getvalue()).decode("utf-8")
        print(f"[GEMINI] Image personnage: {len(char_b64)} chars")

        user_buffer = io.BytesIO()
        self.captured_photo.save(user_buffer, format="JPEG", quality=85)
        user_b64 = base64.b64encode(user_buffer.getvalue()).decode("utf-8")
        print(f"[GEMINI] Photo visiteur: {len(user_b64)} chars")

        prompt = PROMPTS[style].format(name=character["name"])
        print(f"[GEMINI] Envoi requete...")

        request_body = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": char_b64}},
                    {"inline_data": {"mime_type": "image/jpeg", "data": user_b64}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "temperature": 1,
                "topP": 0.95
            }
        }

        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        request_data = json.dumps(request_body).encode("utf-8")

        req = urllib.request.Request(url, data=request_data,
                                     headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                print(f"[GEMINI] Reponse recue - cles: {list(result.keys())}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"[GEMINI] ERREUR HTTP {e.code}: {error_body[:300]}")
            raise Exception(f"Erreur Gemini HTTP {e.code}: {error_body[:80]}")
        except urllib.error.URLError as e:
            print(f"[GEMINI] ERREUR CONNEXION: {e.reason}")
            raise Exception(f"Erreur connexion: {e.reason}")

        candidates = result.get("candidates", [])
        if not candidates:
            feedback = result.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "inconnu")
            print(f"[GEMINI] AUCUN CANDIDAT - feedback: {feedback}")
            raise Exception(f"Bloque par Gemini: {block_reason}")

        parts = candidates[0].get("content", {}).get("parts", [])
        print(f"[GEMINI] {len(parts)} parts recues")
        for i, part in enumerate(parts):
            if "inlineData" in part:
                print(f"[GEMINI] Part {i}: IMAGE trouvee")
                img_data = base64.b64decode(part["inlineData"]["data"])
                return Image.open(io.BytesIO(img_data))
            elif "text" in part:
                print(f"[GEMINI] Part {i}: texte: {part['text'][:80]}")

        finish_reason = candidates[0].get("finishReason", "inconnu")
        print(f"[GEMINI] PAS D IMAGE - finishReason: {finish_reason}")
        raise Exception(f"Pas d image generee (raison: {finish_reason})")

    def generate_qr_code(self):
        """Uploader le selfie et une page HTML sur S3, afficher QR code"""
        try:
            self.root.after(0, lambda: self.qr_status.configure(text="Preparation...", fg="#888"))

            import boto3
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_filename = f"selfie-{timestamp}.jpg"
            html_filename = f"selfie-{timestamp}.html"

            # Sauvegarder localement
            filepath = os.path.join(OUTPUT_DIR, img_filename)
            self.result_image.save(filepath, "JPEG", quality=92)

            # Uploader image sur S3
            s3 = boto3.client("s3", region_name="us-east-1")
            bucket = os.environ.get("S3_BUCKET_NAME", "votre-bucket-s3")
            s3.upload_file(filepath, bucket, img_filename, ExtraArgs={"ContentType": "image/jpeg"})

            # Generer lien presigne pour l image (24h)
            img_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": img_filename},
                ExpiresIn=172800
            )

            # Generer la page HTML
            html_content = self.build_selfie_html(img_url)
            html_path = os.path.join(OUTPUT_DIR, html_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Uploader la page HTML sur S3
            s3.upload_file(html_path, bucket, html_filename, ExtraArgs={"ContentType": "text/html; charset=utf-8"})

            # Generer lien presigne pour la page HTML (24h)
            page_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": html_filename},
                ExpiresIn=172800
            )

            # Generer le QR code vers la page HTML
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(page_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.resize((250, 250), Image.LANCZOS)
            qr_photo = ImageTk.PhotoImage(qr_img)

            self.root.after(0, lambda: self._display_qr(qr_photo))
        except Exception as e:
            self.root.after(0, lambda: self.qr_status.configure(
                text=f"Erreur: {str(e)[:30]}", fg="#ff6b6b"))

    def build_selfie_html(self, img_url):
        """Generer la page HTML avec le selfie et les messages"""
        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ton Selfie - La Particule du Diable</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            text-align: center;
        }}
        h1 {{
            color: #FFD700;
            font-size: 1.4em;
            margin-bottom: 5px;
        }}
        .selfie-img {{
            width: 100%;
            max-width: 500px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            margin: 15px 0;
        }}
        .section {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            text-align: left;
        }}
        .section h2 {{
            color: #87ceeb;
            font-size: 1.1em;
            margin-top: 0;
        }}
        a {{
            color: #FFD700;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .download-btn {{
            display: inline-block;
            background: #27ae60;
            color: white;
            padding: 12px 25px;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: bold;
            text-decoration: none;
            margin: 10px 0;
        }}
        .signature {{
            color: #888;
            margin-top: 20px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Merci d avoir rencontre un personnage de La Particule du Diable!</h1>
        <img src="{img_url}" alt="Ton selfie" class="selfie-img">
        <p class="instruction">Appuie longtemps sur l'image pour l'enregistrer dans tes photos</p>

        <div class="section">
            <h2>Emilie souhaite te parler depuis l au-dela...</h2>
            <p>Elle repondra a tes questions sur son histoire, sa famille et le mystere qui menace notre univers.</p>
            <p><a href="https://michelbargoneauteur.com/ghostmessenger">Parle avec elle ici</a></p>
        </div>

        <div class="section">
            <h2>Gagne le livre audio!</h2>
            <p>2 chances (cumulatives) :</p>
            <p>1. Publie ton selfie en identifiant <strong>@michelbargoneauteur</strong></p>
            <p>2. Suis la page <a href="https://facebook.com/michelbargoneauteur">facebook.com/michelbargoneauteur</a></p>
            <p>Fais les deux et double tes chances!</p>
            <p><em>Concours jusqu au 30 aout. Gagnant annonce sur la page d auteur.</em></p>
        </div>

        <p class="signature">- Michel Bargone</p>
    </div>
</body>
</html>"""

    def _display_qr(self, qr_photo):
        """Afficher le QR code a l ecran"""
        self.qr_label.configure(image=qr_photo)
        self.qr_label.image = qr_photo
        self.qr_status.configure(text="Valide 48h", fg="#27ae60")

    def send_sms(self):
        phone = self.phone_entry.get().strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10:
            self.sms_status.configure(text="Numero invalide", fg="#ff6b6b")
            return

        if not phone.startswith("+"):
            phone = "+1" + digits

        self.btn_sms.configure(state=tk.DISABLED, text="Envoi...")
        self.sms_status.configure(text="", fg="#888")

        def do_send():
            try:
                import boto3
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"selfie-sms-{timestamp}.jpg"

                # Sauvegarder localement
                filepath = os.path.join(OUTPUT_DIR, filename)
                self.result_image.save(filepath, "JPEG", quality=92)

                # Uploader sur S3
                s3 = boto3.client("s3", region_name="us-east-1")
                bucket = os.environ.get("S3_BUCKET_NAME", "votre-bucket-s3")
                s3.upload_file(filepath, bucket, filename, ExtraArgs={"ContentType": "image/jpeg"})

                # Generer lien presigne (24h)
                presigned_url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": filename},
                    ExpiresIn=172800
                )

                # Envoyer via SNS
                sns = boto3.client("sns", region_name="us-east-1")

                # SMS 1: Selfie + Emilie
                message1 = (
                    f"Merci d'avoir rencontré un personnage de La Particule du Diable!\n\n"
                    f"Ton selfie souvenir:\n{presigned_url}\n\n"
                    f"Émilie souhaite te parler depuis l'au-delà...\n"
                    f"Parle avec elle ici: https://michelbargoneauteur.com/ghostmessenger\n\n"
                    f"Bonne exploration...\n\n"
                    f"- Michel Bargone"
                )
                sns.publish(
                    PhoneNumber=phone,
                    Message=message1,
                    MessageAttributes={
                        "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
                    }
                )

                # Attendre 5 secondes pour que le premier SMS arrive avant le second
                time.sleep(5)

                # SMS 2: Concours
                message2 = (
                    f"Gagne le livre audio de La Particule du Diable! "
                    f"2 chances (cumulatives):\n\n"
                    f"1- Publie ton selfie en identifiant @michelbargoneauteur\n"
                    f"2- Suis la page facebook.com/michelbargoneauteur\n\n"
                    f"Fais les deux et double tes chances!\n\n"
                    f"Concours jusqu'au 30 aout. Gagnant annonc\u00e9 sur ma page d'auteur.\n\n"
                    f"- Michel Bargone"
                )
                sns.publish(
                    PhoneNumber=phone,
                    Message=message2,
                    MessageAttributes={
                        "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
                    }
                )
                self.root.after(0, lambda: self.sms_status.configure(text="SMS envoye!", fg="#27ae60"))
            except Exception as e:
                self.root.after(0, lambda: self.sms_status.configure(text=f"Erreur: {str(e)[:30]}", fg="#ff6b6b"))
            finally:
                self.root.after(0, lambda: self.btn_sms.configure(state=tk.NORMAL, text="Envoyer"))

        threading.Thread(target=do_send, daemon=True).start()

    def show_result(self):
        if self.result_image:
            display = self.result_image.copy()
            display.thumbnail((700, 450), Image.LANCZOS)
            photo = ImageTk.PhotoImage(display)
            self.result_label.configure(image=photo)
            self.result_label.image = photo
            self.show_step(4)
            # Generer QR code en arriere-plan
            threading.Thread(target=self.generate_qr_code, daemon=True).start()

    def show_error(self, message):
        self.loading_label.configure(text=f"Erreur: {message}", fg="#ff6b6b")
        self.root.after(3000, self.restart)

    def show_error_with_options(self, message):
        """Affiche l erreur avec options apres 3 tentatives echouees"""
        self.loading_label.configure(
            text=f"Echec apres 3 essais:\n{message[:60]}",
            fg="#ff6b6b")
        self.progress_label.configure(text="")

        # Creer un frame pour les boutons d option
        if hasattr(self, "error_btn_frame"):
            self.error_btn_frame.destroy()
        self.error_btn_frame = tk.Frame(self.step3_frame, bg="#1a1a2e")
        self.error_btn_frame.pack(pady=20)

        btn_retry = tk.Button(self.error_btn_frame,
                              text="Reessayer (garder la photo)",
                              font=("Arial", 13, "bold"), bg="#e67e22", fg="white",
                              command=self.retry_with_same_photo, relief=tk.FLAT,
                              padx=20, pady=10, cursor="hand2")
        btn_retry.pack(pady=8)

        btn_retake = tk.Button(self.error_btn_frame,
                               text="Reprendre la photo",
                               font=("Arial", 13, "bold"), bg="#4a90e2", fg="white",
                               command=self.retry_with_new_photo, relief=tk.FLAT,
                               padx=20, pady=10, cursor="hand2")
        btn_retake.pack(pady=8)

    def retry_with_same_photo(self):
        """Relancer la generation avec la meme photo"""
        if hasattr(self, "error_btn_frame"):
            self.error_btn_frame.destroy()
        self.loading_label.configure(text="Generation en cours...", fg="#87ceeb")
        self.progress_label.configure(text="Veuillez patienter (15-30 secondes)")
        threading.Thread(target=self.generate_selfie, daemon=True).start()

    def retry_with_new_photo(self):
        """Retourner a la camera pour reprendre la photo"""
        if hasattr(self, "error_btn_frame"):
            self.error_btn_frame.destroy()
        self.loading_label.configure(text="Generation en cours...", fg="#87ceeb")
        self.progress_label.configure(text="Veuillez patienter (15-30 secondes)")
        self.captured_photo = None
        self.show_step(2)

    def save_result(self):
        if self.result_image:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            style = self.selected_style.get()
            char_name = CHARACTERS[self.current_character_index]["name"]
            filename = f"selfie_{style}_{char_name}_{timestamp}.jpg"
            filepath = os.path.join(OUTPUT_DIR, filename)
            self.result_image.save(filepath, "JPEG", quality=92)
            print(f"Sauvegarde: {filepath}")

    def restart(self):
        self.captured_photo = None
        self.result_image = None
        self.loading_label.configure(text="Generation en cours...", fg="#87ceeb")
        self.show_step(1)

    def run(self):
        self.root.mainloop()
        self.stop_camera()


if __name__ == "__main__":
    app = SelfieApp()
    app.run()