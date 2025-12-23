import pandas as pd

# Read Excel file
xls = pd.ExcelFile('Spettri-NTCver.1.0.3.xlsx')

print("=== ANALISI FOGLIO 'Intro' ===")
df_intro = pd.read_excel(xls, 'Intro', header=None)
print(df_intro.head(30))

print("\n=== ANALISI FOGLIO 'Fase1' ===")
df_fase1 = pd.read_excel(xls, 'Fase1', header=None)
print(df_fase1.head(30))

print("\n=== ANALISI FOGLIO 'Fase2' ===")
df_fase2 = pd.read_excel(xls, 'Fase2', header=None)
print(df_fase2.head(30))
