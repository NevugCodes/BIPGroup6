import base64
from openai import OpenAI
from pathlib import Path

client = OpenAI()

def encode_image(path):
    """Liest eine lokale Bilddatei ein und gibt sie base64-kodiert zurück"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def main():
    # Dein Prompt
    prompt = "Beschreibe mir das Objekt auf diesen Bildern"

    # Liste von lokalen Bildern
    image_paths = [
        Path("output/aeg/1-1997-0457-000-000.JPG"),
        Path("output/aeg/1-1997-0457-000-001.JPG")
    ]

    # Baue die Eingabe-Nachricht mit Base64-kodierten Bildern
    content = [{"type": "text", "text": prompt}]
    for path in image_paths:
        image_b64 = encode_image(path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_b64}"
            }
        })

    # Anfrage an OpenAI
    response = client.chat.completions.create(
        model="gpt-4o-mini",   # oder gpt-4o / gpt-4.1
        messages=[
            {"role": "user", "content": content}
        ]
    )

    # Ausgabe
    print("Antwort:", response.choices[0].message.content)

if __name__ == "__main__":
    main()
