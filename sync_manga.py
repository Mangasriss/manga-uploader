import json
import os
import requests
from bs4 import BeautifulSoup
import cloudinary
from cloudinary.uploader import upload
import logging
from io import BytesIO

# 🔧 Configuration Cloudinary
cloudinary.config(
    cloud_name="dgvucrd8b",
    api_key="582649391869225",
    api_secret="XcFEhFsJd06IkkSt2NztFOlkCkk"
)

# 🔧 Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 📁 JSON pour suivre ce qui a été uploadé
json_path = "chapters.json"

mangas_suivis = []
base_url = "https://mangamoins.shaeishu.co/"

def charger_json():
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_json(historique):
    with open(json_path, "w") as f:
        json.dump(historique, f, indent=2)

def extraire_derniers_chapitres():
    logging.info("📡 Extraction des chapitres...")
    historique = charger_json()
    chapitres_par_manga = {}

    for manga in mangas_suivis:
        chapitres_par_manga[manga] = []
        page = 1
        trouve_10 = False
        max_pages = None

        while not trouve_10:
            url = f"{base_url}?p={page}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")
            if max_pages is None:
                pagination = soup.find("div", class_="pages")
                if pagination:
                    try:
                        max_pages = max([int(a.text) for a in pagination.find_all("a") if a.text.isdigit()])
                    except:
                        max_pages = 1

            sorties = soup.find_all("div", class_="sortie")
            for sortie in sorties:
                p_tag = sortie.find("p")
                manga_nom = p_tag.contents[0].strip() if p_tag else ""
                if manga_nom != manga:
                    continue

                titre = sortie.find("div", class_="sortiefooter").p.text.strip()
                scan_id = sortie.find("a")["href"].split("=")[-1]
                numero = sortie.find("h3").text.strip().replace("#", "")

                chapitres_par_manga[manga].append({
                    "nom_manga": manga_nom,
                    "numero": numero,
                    "titre": titre,
                    "scan_id": scan_id
                })

                if len(chapitres_par_manga[manga]) >= 10:
                    trouve_10 = True
                    break

            if max_pages and page >= max_pages:
                break
            page += 1

    return chapitres_par_manga

def nettoyer_nom(nom):
    return nom.replace("/", "_").strip()

def uploader_chapitre(chap):
    historique = charger_json()
    cle = f"{chap['nom_manga']}|{chap['numero']}"
    if chap["nom_manga"] in historique and cle in historique[chap["nom_manga"]]:
        logging.info(f"✅ {cle} déjà uploadé, on skip.")
        return

    logging.info(f"⬆️ Upload du chapitre {cle}")
    i = 1

    nom_manga_clean = nettoyer_nom(chap['nom_manga'])
    titre_clean = nettoyer_nom(chap['titre'])
    dossier_cloud = f"Manga/{nom_manga_clean}/Chapitre {chap['numero']} - {titre_clean}"

    while True:
        num_img = str(i).zfill(2)
        image_url = f"{base_url}files/scans/{chap['scan_id']}/{num_img}.png"
        logging.info(f"📷 Téléchargement image : {image_url}")
        try:
            resp = requests.get(image_url, timeout=10)
            if resp.status_code != 200:
                logging.info(f"⛔ Image {num_img}.png non trouvée, arrêt.")
                break

            result = upload(
                file=BytesIO(resp.content),
                folder=dossier_cloud,
                public_id=num_img,
                resource_type="image",
                overwrite=True
            )

            logging.info(f"✅ Image {i} uploadée : {result.get('secure_url')}")
            i += 1

        except Exception as e:
            logging.error(f"❌ Erreur upload image {i} : {e}")
            break

    # MAJ JSON local
    historique.setdefault(chap["nom_manga"], []).append(cle)
    if len(historique[chap["nom_manga"]]) > 10:
        ancien = historique[chap["nom_manga"]].pop(0)
        logging.info(f"🗑️ À supprimer manuellement : {ancien}")

    sauvegarder_json(historique)

def lancer_bot():
    chapitres_par_manga = extraire_derniers_chapitres()
    for manga, chapitres in chapitres_par_manga.items():
        for chap in chapitres:
            uploader_chapitre(chap)

if __name__ == "__main__":
    lancer_bot()
