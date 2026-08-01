import os, json, urllib.request

OLLAMA_URL = os.environ.get("ANAMNESIS_OLLAMA_URL", "http://localhost:11434/api/embeddings")
MODEL = os.environ.get("ANAMNESIS_EMBED_MODEL", "nomic-embed-text")
BODY_CAP = 3000  # keep Title+Type+Description header + body under the embed model's context


def build_payload(name, typ, description, body):
    header = f"Title: {name}\nType: {typ}\nDescription: {description}\n\nBody:\n"
    return header + (body or "")[:BODY_CAP]


def embed(text, model=MODEL, url=OLLAMA_URL, timeout=30):
    data = json.dumps({"model": model, "prompt": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["embedding"]
