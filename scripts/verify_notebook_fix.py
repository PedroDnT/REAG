"""
Quick verification that notebooks can find data files
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config

config = Config()

print("="*70)
print("🔍 VERIFICAÇÃO DE ARQUIVOS DE DADOS")
print("="*70)

# Check Cadastro
print("\n📂 Procurando Cadastro...")
cadastro_files = list(config.RAW_DATA_DIR.glob('cad_fi*.csv'))
cadastro_dir = config.RAW_DATA_DIR / 'cadastro'
if cadastro_dir.exists():
    cadastro_files.extend(list(cadastro_dir.glob('cad_fi*.csv')))

if cadastro_files:
    print(f"✅ {len(cadastro_files)} arquivo(s) de cadastro encontrado(s):")
    for f in cadastro_files:
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"   - {f.relative_to(config.RAW_DATA_DIR.parent)}: {size_mb:.1f} MB")
else:
    print("❌ Nenhum arquivo de cadastro encontrado")
    print(f"   Procurado em: {config.RAW_DATA_DIR}")
    print("   Padrão: cad_fi*.csv")

# Check Informe Diário
print("\n📂 Procurando Informe Diário...")
informe_files = sorted(config.RAW_DATA_DIR.glob('inf_diario_fi_*.csv'))
informe_dir = config.RAW_DATA_DIR / 'informe'
if informe_dir.exists():
    informe_files.extend(list(informe_dir.glob('inf_diario_fi_*.csv')))

if informe_files:
    print(f"✅ {len(informe_files)} arquivo(s) de informe encontrado(s):")
    for f in sorted(set(informe_files))[:5]:  # Show first 5
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"   - {f.name}: {size_mb:.1f} MB")
    if len(informe_files) > 5:
        print(f"   ... e mais {len(informe_files) - 5} arquivo(s)")
else:
    print("❌ Nenhum arquivo de informe encontrado")
    print(f"   Procurado em: {config.RAW_DATA_DIR}")
    print("   Padrão: inf_diario_fi_*.csv")

# Check CDA
print("\n📂 Procurando CDA...")
cda_files = sorted(config.RAW_DATA_DIR.glob('cda_*.csv'))
cda_dir = config.RAW_DATA_DIR / 'cda'
if cda_dir.exists():
    cda_files.extend(list(cda_dir.glob('cda_*.csv')))

if cda_files:
    print(f"✅ {len(cda_files)} arquivo(s) de CDA encontrado(s):")
    for f in sorted(set(cda_files))[:5]:
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"   - {f.name}: {size_mb:.1f} MB")
    if len(cda_files) > 5:
        print(f"   ... e mais {len(cda_files) - 5} arquivo(s)")
else:
    print("❌ Nenhum arquivo de CDA encontrado")
    print(f"   Procurado em: {config.RAW_DATA_DIR}")
    print("   Padrão: cda_*.csv")

print("\n" + "="*70)

# Summary
has_cadastro = len(cadastro_files) > 0
has_informe = len(informe_files) > 0
has_cda = len(cda_files) > 0

if has_cadastro and has_informe:
    print("✅ NOTEBOOKS PODEM SER EXECUTADOS")
    print("\nPróximos passos:")
    print("   1. Execute: notebooks/02_identify_reag_funds.ipynb")
    print("   2. Execute: notebooks/03_flow_analysis.ipynb")
    if has_cda:
        print("   3. Execute: notebooks/04_anomaly_detection.ipynb")
        print("   4. Execute: notebooks/05_advanced_market_analysis.ipynb")
elif not has_cadastro:
    print("⚠️  CADASTRO NÃO ENCONTRADO")
    print("\nExecute: notebooks/01_data_collection.ipynb")
elif not has_informe:
    print("⚠️  INFORME DIÁRIO NÃO ENCONTRADO")
    print("\nExecute: notebooks/01_data_collection.ipynb")

print("="*70)
