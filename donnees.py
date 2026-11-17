"""Base de démo « Maison Lumière » — nov. 2024 → oct. 2026.
Catalogue inspiré d'une vraie boutique ; clients et ventes 100 % FICTIFS."""
import os
import random
import sqlite3
from datetime import date, timedelta

DB = os.getenv("DATA_DB", "maison_verde.db")
random.seed(42)

PRODUITS = {
    "Mugs artisanaux": [
        ("Mug avec paille artisanal en céramique – Fleurs et citrons", 29), ("Mug avec paille artisanal en céramique – Œil Nazar", 29),
        ("Mug artisanal en céramique – Deauville", 29), ("Mug artisanal en céramique – Pissenlit", 29),
        ("Mug artisanal en céramique – Cactus", 29), ("Mug artisanal en céramique – Fraises", 29),
        ("Mug artisanal en céramique – Œil multiple", 29), ("Mug artisanal en céramique – Marilyn", 29),
        ("Mug artisanal en céramique – Arbre de vie", 29), ("Mug artisanal en céramique – Frida Kahlo", 29),
        ("Mug artisanal en céramique – Œil Nazar", 29)],
    "Théières & cezves": [
        ("Théière ÇINTEMANI – KORKMAZ", 79), ("Théière RIVA Rouge – KORKMAZ", 69), ("Théière DEMIKS INOX – KORKMAZ", 139),
        ("Théière VERTEX – KORKMAZ", 139), ("Théière STEAMA – KORKMAZ", 75), ("Théière DROPPA MIDI – KORKMAZ", 69),
        ("Théière BELLA ROSE GOLD – KORKMAZ", 79), ("Théière BELLA NORA – KORKMAZ", 79),
        ("Cafetière Traditionnelle Cezve Classic 0,5L – KORKMAZ", 35), ("Plateau de service Café Perla – KORKMAZ", 55),
        ("Bouilloire Tombik – KORKMAZ", 59)],
    "Kimonos Eden.K": [
        ("Kimono LE NAZAR – Eden.K", 89), ("Kimono L'HARMONIE MARRON – Eden.K", 99), ("Kimono L'HARMONIE BLEUE – Eden.K", 99),
        ("Kimono L'HARMONIE ROSE – Eden.K", 99), ("Kimono L'ŒIL SCINTILLANT – Eden.K", 89), ("Kimono L'ŒIL AZUR – Eden.K", 99),
        ("Kimono LE LEOPARD – Eden.K", 89), ("Kimono LE LEOPARD NOIR – Eden.K", 89), ("Kimono LE SOLEIL – Eden.K", 89),
        ("Kimono FRIDA KAHLO – Eden.K", 89), ("Kimono LA FEMME – Eden.K", 89),
        ("Pantalon de Kimono Rose – Eden.K", 59), ("Pantalon de Kimono Bleu – Eden.K", 59), ("Pantalon de Kimono Beige – Eden.K", 49)],
    "Linge de maison": [
        ("Couverture – Plaid en gaze de coton 4 épaisseurs Beige", 99), ("Couverture – Plaid en gaze de coton 4 épaisseurs Moutarde", 99),
        ("Couverture – Plaid en gaze de coton 4 épaisseurs Bleu", 99), ("Couverture – Plaid en gaze de coton 4 épaisseurs Rose", 99),
        ("Serviette mains coton nid d'abeille blanche 45x75", 24), ("Serviette mains coton nid d'abeille cappuccino 45x75", 24),
        ("Serviette de bain coton nid d'abeille blanche 100x200", 59), ("Serviette de bain coton nid d'abeille cappuccino 100x200", 59),
        ("Peignoir en coton nid d'abeille blanc", 89), ("Peignoir en coton nid d'abeille cappuccino", 89)],
    "Arts de la table": [
        ("Service de table FULL MOON 27 pièces pour 6 personnes", 229), ("Couverts DILRUBA 84 pièces GOLD – KORKMAZ", 449),
        ("Couverts DILRUBA 84 pièces INOX – KORKMAZ", 349), ("Verre RUBY en borosilicate lot de 6", 20),
        ("Verre MIA en borosilicate lot de 6", 22), ("Verre MIA allongé en borosilicate 500 ml lot de 6", 22),
        ("Mug JANE", 5.5), ("Mug LISA", 5.5)],
    "Cuisine": [
        ("Ustensiles de cuisine NORA 5 pièces – KORKMAZ", 29.9), ("Casseroles Nora 5,5L – KORKMAZ", 79),
        ("Casseroles Nora 3,4L – KORKMAZ", 79), ("Casseroles ALPHA 7L A1030 – KORKMAZ", 99),
        ("Casseroles ALPHA 8,5L A1028 – KORKMAZ", 109), ("Batterie de cuisine ALPHA 9 pièces – KORKMAZ", 259),
        ("Batterie de cuisine VERTEX 8 pièces – KORKMAZ", 299), ("Batterie de cuisine GRANITA 7 pièces – KORKMAZ", 229)],
}
# Popularité relative (les petits prix partent plus souvent que les batteries de cuisine)
POIDS_CATEGORIES = {"Mugs artisanaux": 30, "Théières & cezves": 18, "Kimonos Eden.K": 16,
                    "Linge de maison": 20, "Arts de la table": 10, "Cuisine": 6}

VILLES = ["Villiers-le-Bel", "Sarcelles", "Saint-Brice-sous-Forêt", "Écouen", "Garges-lès-Gonesse", "Gonesse",
          "Paris", "Lyon", "Marseille", "Bordeaux", "Lille", "Nantes", "Toulouse"]
POIDS_VILLES = [24, 15, 10, 7, 8, 6, 12, 3, 4, 3, 3, 3, 2]
LOCALES = set(VILLES[:6])
PRENOMS = ["Camille", "Léa", "Sarah", "Inès", "Nadia", "Chloé", "Yasmine", "Manon", "Sophie", "Myriam", "Julie", "Emma",
           "Laura", "Sonia", "Rachel", "Alice", "Karim", "Thomas", "David", "Lina"]
NOMS = ["Martin", "Benali", "Dubois", "Cohen", "Robert", "Haddad", "Petit", "Durand", "Leroy", "Moreau", "Simon",
        "Laurent", "Lefebvre", "Michel", "Garcia", "Bensoussan", "Bertrand", "Roux", "Diallo", "Fournier"]

DEBUT, FIN = date(2024, 11, 1), date(2026, 10, 27)
# Noël très fort, fête des mères en mai, creux en été et en janvier-février
SAISON = {1: 0.7, 2: 0.7, 3: 0.85, 4: 0.9, 5: 1.5, 6: 1.0, 7: 0.75, 8: 0.6, 9: 0.9, 10: 1.0, 11: 1.4, 12: 2.3}


def generer():
    if os.path.exists(DB):
        os.remove(DB)
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE clients (id INTEGER PRIMARY KEY, nom TEXT, ville TEXT, segment TEXT, inscrit_le TEXT);
    CREATE TABLE produits (id INTEGER PRIMARY KEY, nom TEXT, categorie TEXT, prix_unitaire REAL);
    CREATE TABLE commandes (id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES clients(id), date TEXT,
                            canal TEXT, statut TEXT);
    CREATE TABLE lignes_commande (id INTEGER PRIMARY KEY, commande_id INTEGER REFERENCES commandes(id),
                                  produit_id INTEGER REFERENCES produits(id), quantite INTEGER, prix_unitaire REAL);
    """)

    par_cat = {}
    for cat, items in PRODUITS.items():
        for nom, prix in items:
            cur = c.execute("INSERT INTO produits (nom, categorie, prix_unitaire) VALUES (?, ?, ?)", (nom, cat, prix))
            par_cat.setdefault(cat, []).append((cur.lastrowid, prix))

    clients = []
    for _ in range(380):
        ville = random.choices(VILLES, POIDS_VILLES)[0]
        if random.random() < 0.4:   # clientèle déjà fidèle avant la période
            inscrit = DEBUT - timedelta(days=random.randint(1, 700))
        else:
            inscrit = DEBUT + timedelta(days=random.randint(0, (FIN - DEBUT).days - 30))
        cur = c.execute("INSERT INTO clients (nom, ville, segment, inscrit_le) VALUES (?, ?, ?, ?)",
                        (f"{random.choice(PRENOMS)} {random.choice(NOMS)}", ville, "Particulier", inscrit.isoformat()))
        clients.append((cur.lastrowid, inscrit, ville))

    jour = DEBUT
    while jour <= FIN:
        croissance = 1 + 0.15 * (jour - DEBUT).days / (FIN - DEBUT).days
        nb = max(0, round(random.gauss(1.8, 1.0) * SAISON[jour.month] * croissance))
        if jour.weekday() == 5:      # le samedi, plus de passage
            nb = round(nb * 1.5)
        eligibles = [cl for cl in clients if cl[1] <= jour]
        for _ in range(nb if eligibles else 0):
            cid, _, ville = random.choice(eligibles)
            if ville not in LOCALES:
                canal = "Site web"
            else:
                canal = random.choices(["Boutique", "Site web"], [75, 25])[0]
            statut = random.choices(["livrée", "annulée", "retournée"], [94, 3, 3])[0]
            cur = c.execute("INSERT INTO commandes (client_id, date, canal, statut) VALUES (?, ?, ?, ?)",
                            (cid, jour.isoformat(), canal, statut))
            for _ in range(random.choices([1, 2, 3], [65, 27, 8])[0]):
                pc = dict(POIDS_CATEGORIES)
                if jour.month == 5:
                    pc["Kimonos Eden.K"] += 18; pc["Mugs artisanaux"] += 10   # fête des mères
                if jour.month in (11, 12):
                    pc["Théières & cezves"] += 12; pc["Arts de la table"] += 6  # cadeaux de Noël
                if jour.month in (6, 7, 8):
                    pc["Linge de maison"] += 10                               # serviettes, peignoirs l'été
                cat = random.choices(list(pc), list(pc.values()))[0]
                items = par_cat[cat]   # dans une catégorie, les articles chers se vendent moins souvent
                pid, prix = random.choices(items, [1 / p ** 1.2 for _, p in items])[0]
                qte = random.choices([1, 2], [88, 12])[0]
                c.execute("INSERT INTO lignes_commande (commande_id, produit_id, quantite, prix_unitaire) VALUES (?, ?, ?, ?)",
                          (cur.lastrowid, pid, qte, prix))
        jour += timedelta(days=1)

    c.commit()
    n = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ["clients", "produits", "commandes", "lignes_commande"]}
    c.close()
    return n


if __name__ == "__main__":
    print("Base générée :", generer())