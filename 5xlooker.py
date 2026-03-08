import pandas as pd
from pathlib import Path

path = Path(r"C:\Python\5x1000\Dati")

files = sorted(path.glob("dati_*.xlsx"))

df_list = []

for f in files:
    anno = f.stem.split("_")[1]
    df = pd.read_excel(f)
    df["ANNO"] = int(anno)
    df_list.append(df)

df = pd.concat(df_list)

df.to_csv("enti_5x1000.csv", index=False)