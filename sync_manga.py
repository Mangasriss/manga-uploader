import json
import os
import requests
from bs4 import BeautifulSoup
import cloudinary
from cloudinary.uploader import upload
from cloudinary.api import delete_resources_by_prefix, delete_folder
import logging
from io import BytesIO

# 🔧 Configuration Cloudinary
cloudinary.config(
    cloud_name="dgvucrd8b",
    api_key="582649391869225",
    api_secret="XcFEhFsJd06IkkSt2NztFOlkCkk"
)

# 📁 Logs console + fichier
logfile_path = "logfile.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logfile_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 📁 JSON pour suivre ce qui a été uploadé
json_path = "chapters.json"
base_url = "https://mangamoins.shaeishu.co/"

def lire_mangas_suivis():
    if os.path.exists("mangas.txt"):
        with open("mangas.txt", "r", encoding="utf-8") as f:
            return [ligne.strip() for ligne in f.readlines() if ligne.strip()]
    return []

def charger_json():
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def sauvegarder_json(historique):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2)

def nettoyer_nom(nom):
    return nom.replace("/", "_").strip()

def supprimer_ancien_dossier_cloudinary(nom_manga, numero, titre):
    nom_manga_clean = nettoyer_nom(nom_manga)
    titre_clean = nettoyer_nom(titre)
    dossier = f"Manga/{nom_manga_clean}/Chapitre {numero} - {titre_clean}"
    try:
        delete_resources_by_prefix(dossier)
        delete_folder(dossier)
        logging.info(f"🧹 Dossier supprimé sur Cloudinary : {dossier}")
    except Exception as e:
        logging.warning(f"⚠️ Erreur suppression Cloudinary {dossier} : {e}")

def extraire_derniers_chapitres():
    logging.info("📡 Extraction des chapitres...")
    historique = charger_json()
    mangas_suivis = lire_mangas_suivis()
    chapitres_par_manga = {}

    for manga in mangas_suivis:
        chapitres_par_manga[manga] = []
        page = 1
        trouve_10 = False
        max_pages = None

        while not trouve_10:
            url = f"{base_url}?p={page}"
            try:
                response = requests.get(url, timeout=10)
            except Exception as e:
                logging.warning(f"❌ Erreur connexion page {url} : {e}")
                break

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

    historique.setdefault(chap["nom_manga"], []).append(cle)

    # Limite à 10 chapitres → supprimer le plus ancien
    if len(historique[chap["nom_manga"]]) > 10:
        ancien = historique[chap["nom_manga"]].pop(0)
        nom, numero = ancien.split("|")
        supprimer_ancien_dossier_cloudinary(nom, numero, chap["titre"])

    sauvegarder_json(historique)

def lancer_bot():
    chapitres_par_manga = extraire_derniers_chapitres()
    for manga, chapitres in chapitres_par_manga.items():
        for chap in chapitres:
            uploader_chapitre(chap)

if __name__ == "__main__":
    lancer_bot()
