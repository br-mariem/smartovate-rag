"""
US 1.1 : Extraction du texte des documents
- Lit les fichiers depuis S3 (dossier raw/)
- Extrait le texte proprement (via unstructured, préserve les tableaux)
- Nettoie le texte (caractères spéciaux inutiles, sauts de ligne)
- Sauvegarde le résultat + métadonnées dans S3 (dossier processed/)
"""

import boto3
import os
import re
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from unstructured.partition.auto import partition

load_dotenv()

REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3 = boto3.client("s3", region_name=REGION)


def clean_text(text: str) -> str:
    """Nettoie le texte extrait : espaces multiples, sauts de ligne excessifs."""
    text = re.sub(r"[ \t]+", " ", text)          # espaces/tabs multiples -> un seul espace
    text = re.sub(r"\n{3,}", "\n\n", text)         # plus de 2 sauts de ligne -> 2 max
    text = text.strip()
    return text


def extract_text_from_file(local_path: str) -> str:
    """Extrait le texte d'un fichier local (PDF, DOCX, MD...) via unstructured.
    Utilise hi_res pour les PDF afin de préserver la structure des tableaux (Bug 3)."""
    ext = os.path.splitext(local_path)[1].lower()

    if ext == ".pdf":
        elements = partition(filename=local_path, strategy="hi_res", infer_table_structure=True)
    else:
        elements = partition(filename=local_path)

    text_parts = []
    for el in elements:
        # Si l'élément est un tableau, on récupère sa version HTML structurée si disponible
        if el.category == "Table" and hasattr(el.metadata, "text_as_html") and el.metadata.text_as_html:
            text_parts.append(el.metadata.text_as_html)
        else:
            text_parts.append(str(el))

    return "\n\n".join(text_parts)


def list_raw_documents():
    """Liste tous les fichiers présents dans le dossier raw/ du bucket."""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="raw/")
    if "Contents" not in response:
        return []
    # On ignore les entrées qui sont juste le dossier lui-même (taille 0, se termine par /)
    return [obj["Key"] for obj in response["Contents"] if not obj["Key"].endswith("/")]


def process_document(s3_key: str):
    """Télécharge, extrait, nettoie, et réuploade un document."""
    filename = os.path.basename(s3_key)
    print(f"\n--- Traitement de : {filename} ---")

    # Télécharger le fichier dans un dossier temporaire local
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = os.path.join(tmp_dir, filename)
        s3.download_file(BUCKET_NAME, s3_key, local_path)

        # Récupérer les métadonnées S3 (date de dernière modification)
        head = s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        last_modified = head["LastModified"].isoformat()
        file_size = head["ContentLength"]

        # Extraction du texte
        try:
            raw_text = extract_text_from_file(local_path)
        except Exception as e:
            print(f"  ❌ Erreur d'extraction : {e}")
            return

        cleaned_text = clean_text(raw_text)
        print(f"  ✅ Texte extrait : {len(cleaned_text)} caractères")

        # Préparer le résultat avec métadonnées
        result = {
            "source_file": filename,
            "source_s3_key": s3_key,
            "extraction_date": datetime.utcnow().isoformat(),
            "last_modified": last_modified,
            "file_size_bytes": file_size,
            "char_count": len(cleaned_text),
            "text": cleaned_text,
        }

        # Nom du fichier de sortie (même nom, extension .json)
        output_filename = os.path.splitext(filename)[0] + ".json"
        output_key = f"processed/{output_filename}"

        # Upload du résultat vers S3/processed
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"  ✅ Sauvegardé dans S3 : {output_key}")


def main():
    print("=== US 1.1 : Extraction du texte des documents ===")
    documents = list_raw_documents()

    if not documents:
        print("Aucun document trouvé dans raw/. Uploadez des fichiers avant de relancer ce script.")
        return

    print(f"{len(documents)} document(s) trouvé(s) dans raw/ :")
    for doc in documents:
        print(f"  - {doc}")

    for doc_key in documents:
        process_document(doc_key)

    print("\n=== Traitement terminé ===")


if __name__ == "__main__":
    main()