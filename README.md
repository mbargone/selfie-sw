# Selfie App - Raspberry Pi Edition

## Installation sur Raspberry Pi

```bash
sudo apt update
sudo apt install python3-pip python3-tk python3-pil python3-pil.imagetk
pip3 install opencv-python
```

## Configuration

1. Placez vos images de personnages dans le dossier `personnages/`
2. Configurez votre cle API Gemini:
   ```bash
   export GEMINI_API_KEY="votre_cle_ici"
   ```

## Lancement

```bash
python3 selfie_app.py
```

## Controles

- Fleches gauche/droite: naviguer entre les personnages
- Escape: quitter
- Les selfies sont sauvegardes dans le dossier `output/`

## Styles disponibles

- **Polaroid**: collage local sans IA (instantane)
- **Realiste**: generation IA avec tenue de soiree sur tapis rouge
- **Cartoon**: generation IA style Pixar/Disney 3D