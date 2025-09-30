import pandas as pd
import os
import shutil
from pathlib import Path
import glob

def copy_images_by_object_numbers(excel_path, images_base_path, output_path):
    """
    Kopiert Bilder basierend auf Objektnummern aus einer Excel-Liste.
    
    Args:
        excel_path: Pfad zur Excel-Datei (data/Liste_Schreibmaschinen.xls)
        images_base_path: Basis-Pfad zum images Ordner
        output_path: Ziel-Pfad für die kopierten Bilder
    """
    
    # Excel-Datei einlesen
    print(f"Lese Excel-Datei: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Prüfen ob Spalte T1 existiert
    if 'T1' not in df.columns:
        print("FEHLER: Spalte 'T1' nicht gefunden!")
        print(f"Verfügbare Spalten: {df.columns.tolist()}")
        return
    
    # Output-Ordner erstellen falls nicht vorhanden
    os.makedirs(output_path, exist_ok=True)
    
    # Statistiken
    total_objects = 0
    total_images_copied = 0
    objects_not_found = []
    
    # Durch alle Objektnummern iterieren
    for idx, row in df.iterrows():
        object_number = row['T1']
        
        # Leere Zellen überspringen
        if pd.isna(object_number):
            continue
        
        total_objects += 1
        object_number = str(object_number).strip()
        
        print(f"\n[{idx+1}] Verarbeite Objektnummer: {object_number}")
        
        # Objektnummer parsen: "1/2024/0501 0" -> Jahr extrahieren
        parts = object_number.split('/')
        if len(parts) < 2:
            print(f"  ⚠ Ungültiges Format: {object_number}")
            objects_not_found.append(object_number)
            continue
        
        year = parts[1]
        
        # Dateinamen-Muster erstellen: "/" -> "-", Leerzeichen beibehalten
        # "1/2024/0501 0" -> "1-2024-0501-0*"
        search_pattern = object_number.replace('/', '-')
        
        # Pfad zum Jahresordner
        year_folder = os.path.join(images_base_path, year)
        
        if not os.path.exists(year_folder):
            print(f"  ⚠ Ordner nicht gefunden: {year_folder}")
            objects_not_found.append(object_number)
            continue
        
        # Suche nach allen passenden Bildern
        # Beispiel: 1-2024-0501-0*.JPG (mit Bindestrichen und verschiedenen Endungen)
        search_patterns = [
            f"{search_pattern}*.jpg",
            f"{search_pattern}*.JPG",
            f"{search_pattern}*.jpeg",
            f"{search_pattern}*.JPEG"
        ]
        
        found_images = []
        for pattern in search_patterns:
            search_path = os.path.join(year_folder, pattern)
            found = glob.glob(search_path)
            found_images.extend(found)
        
        if not found_images:
            print(f"  ⚠ Keine Bilder gefunden für Muster: {search_pattern}*")
            objects_not_found.append(object_number)
            continue
        
        # Bilder kopieren
        print(f"  ✓ {len(found_images)} Bild(er) gefunden")
        for image_path in found_images:
            image_name = os.path.basename(image_path)
            dest_path = os.path.join(output_path, image_name)
            
            try:
                shutil.copy2(image_path, dest_path)
                print(f"    → Kopiert: {image_name}")
                total_images_copied += 1
            except Exception as e:
                print(f"    ✗ Fehler beim Kopieren von {image_name}: {e}")
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("ZUSAMMENFASSUNG")
    print("="*60)
    print(f"Verarbeitete Objekte: {total_objects}")
    print(f"Kopierte Bilder: {total_images_copied}")
    print(f"Objekte ohne Bilder: {len(objects_not_found)}")
    
    if objects_not_found:
        print("\nObjekte, für die keine Bilder gefunden wurden:")
        for obj in objects_not_found:
            print(f"  - {obj}")


# Hauptprogramm
if __name__ == "__main__":
    # Pfade anpassen
    excel_file = "data/Liste_Schreibmaschinen.xls"
    images_folder = "images"
    output_folder = "output"
    
    print("Starte Bildkopierung...")
    print(f"Excel-Datei: {excel_file}")
    print(f"Bilder-Ordner: {images_folder}")
    print(f"Ziel-Ordner: {output_folder}")
    
    copy_images_by_object_numbers(excel_file, images_folder, output_folder)
    
    print("\n✓ Fertig!")