Gestion des rendez-vous de radiologie
=====================================

Description
-----------
Cette application desktop locale permet de :
- enregistrer les patients ;
- ajouter, modifier et supprimer des rendez-vous ;
- saisir la date du bon manuellement par l'agent ;
- gerer les types d'examen Échographie, TDM / Scanner, Écho mammaire et IRM ;
- rechercher un patient par nom, CIN ou telephone ;
- filtrer l'affichage par type d'examen et par etat ;
- trier automatiquement les rendez-vous par date du bon en mode croissant ;
- parcourir les resultats avec pagination ;
- saisir manuellement la date de validation finale pour un patient valide au format YYYY-MM-DD ;
- saisir un champ IP obligatoire quand le patient passe a l'etat "Valide" ;
- proteger l'acces du poste avec un nom d'utilisateur et un mot de passe locaux ;
- creer des sauvegardes automatiques de la base SQLite dans le dossier backup/ ;
- acceder aux actions via les boutons, le double-clic ou le clic droit.

Technologies
------------
- Python
- PyQt5
- SQLite

Structure
---------
radiologie_app/
|- build_exe.bat
|- build_setup.bat
|- main.py
|- database.py
|- patients.db
`- README.txt

Lancement
---------
1. Ouvrir un terminal dans le dossier radiologie_app.
2. Installer PyQt5 si necessaire :

   python -m pip install PyQt5

3. Executer :

   python main.py

Remarques
---------
- La date et l'heure du rendez-vous sont attribuees automatiquement par l'application.
- Au premier lancement, l'application demande de creer un acces local avec nom d'utilisateur et mot de passe.
- Ensuite, une connexion est demandee a chaque ouverture du logiciel.
- La date du bon est saisie manuellement par l'agent au format YYYY-MM-DD.
- La date de validation finale est saisie manuellement par l'agent au format YYYY-MM-DD quand le patient passe a l'etat "Valide".
- Le champ IP devient editable et obligatoire uniquement quand le patient passe a l'etat "Valide".
- Une sauvegarde automatique de patients.db est creee apres ajout, modification et suppression, avec conservation des 10 plus recentes.
- La base SQLite est creee automatiquement au premier lancement.
- L'interface graphique depend de PyQt5.
- Raccourcis utiles : Ctrl+N pour ajouter, Suppr pour supprimer, F5 pour actualiser.

Creation de l'executable Windows
--------------------------------
L'icone utilisee pour le .exe doit etre placee dans le fichier :

   icon.ico

Pour construire le logiciel client, executer simplement :

   build_exe.bat

Le script :
- installe PyInstaller si necessaire ;
- genere GestionRadiologie.exe ;
- utilise icon.ico comme icone du logiciel ;
- copie patients.db et README.txt dans le dossier release.

Resultat livre au client :
- release\GestionRadiologie.exe
- release\patients.db
- release\README.txt
- release\icon.ico

Important :
- donnez tout le dossier release au client, pas seulement le .exe ;
- les donnees et les sauvegardes seront creees a cote du .exe ;
- placez le dossier dans un emplacement ou l'utilisateur peut ecrire, par exemple Bureau ou Documents.

Commande manuelle equivalente :

   python -m PyInstaller --onefile --windowed --icon icon.ico --name GestionRadiologie main.py

Creation d'un vrai installateur Windows
---------------------------------------
Pour generer un fichier setup professionnel avec Inno Setup :

   build_setup.bat

Ce script :
- reconstruit d'abord le .exe ;
- utilise le fichier setup_inno.iss ;
- genere un installateur Windows :

   installer\Setup_GestionRadiologie.exe

Important :
- Inno Setup 6 doit etre installe sur le poste ;
- l'installation vise %LocalAppData%\GestionRadiologie pour permettre l'ecriture de patients.db et du dossier backup sans probleme de droits ;
- patients.db est preserve lors d'une reinstallation si le fichier existe deja.
