#!/usr/bin/env python
"""
Script para validar coleta de dados da CVM

Este script testa:
1. Conectividade com CVM
2. Download de Cadastro (arquivo único)
3. Download de Informe Diário
4. Download de CDA
5. Listagem de meses disponíveis
"""
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.cvm_collector import CVMCollector
from config.settings import Config


def main():
    print("="*60)
    print("🔍 VALIDAÇÃO DE COLETA DE DADOS - CVM")
    print("="*60)

    config = Config()
    collector = CVMCollector(config)

    # 1. Verificar conectividade
    print("\n1️⃣  Verificando conectividade com CVM...")
    test_url = collector.get_informe_diario_url(2024, 1)
    if collector.check_file_exists(test_url):
        print("   ✅ Conexão com CVM: OK")
        print(f"   📍 URL testada: {test_url}")
    else:
        print("   ❌ Conexão com CVM: FALHOU")
        print(f"   📍 URL testada: {test_url}")
        print("\n⚠️  Verifique sua conexão com a internet")
        return

    # 2. Testar Cadastro
    print("\n2️⃣  Testando download de Cadastro...")
    print("   📝 Cadastro é um arquivo ÚNICO (cad_fi.csv)")
    try:
        path = collector.download_cadastro(use_current=True)
        if path and path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"   ✅ Cadastro baixado: {path.name}")
            print(f"   💾 Tamanho: {size_mb:.2f} MB")

            # Verificar que é CSV válido
            import pandas as pd
            df = pd.read_csv(path, encoding='latin1', sep=';', nrows=5)
            print(f"   📊 Colunas: {len(df.columns)}")
            print(f"   📏 Primeiras linhas lidas: {len(df)}")
        else:
            print("   ❌ Falha no download de Cadastro")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # 3. Testar Informe Diário
    print("\n3️⃣  Testando download de Informe Diário (Jan/2024)...")
    try:
        path = collector.download_informe_diario(2024, 1)
        if path and path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"   ✅ Informe Diário baixado: {path.name}")
            print(f"   💾 Tamanho: {size_mb:.2f} MB")

            # Verificar que é CSV válido
            import pandas as pd
            df = pd.read_csv(path, encoding='latin1', sep=';', nrows=100)
            print(f"   📊 Colunas: {len(df.columns)}")
            print(f"   📏 Amostra: {len(df)} linhas")
        else:
            print("   ❌ Falha no download de Informe Diário")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # 4. Testar CDA
    print("\n4️⃣  Testando download de CDA (Jan/2024)...")
    try:
        path = collector.download_cda(2024, 1)
        if path and path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"   ✅ CDA baixado: {path.name}")
            print(f"   💾 Tamanho: {size_mb:.2f} MB")

            # Verificar que é CSV válido
            import pandas as pd
            df = pd.read_csv(path, encoding='latin1', sep=';', nrows=100)
            print(f"   📊 Colunas: {len(df.columns)}")
            print(f"   📏 Amostra: {len(df)} linhas")
        else:
            print("   ❌ Falha no download de CDA")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # 5. Listar meses disponíveis
    print("\n5️⃣  Listando meses disponíveis (2024)...")
    print("   ⏳ Verificando disponibilidade (pode demorar)...")
    try:
        # Verificar apenas 2024 para ser mais rápido
        available_informe = collector.get_available_months('informe_diario', 2024, 2024)
        print(f"\n   ✅ Informe Diário 2024: {len(available_informe)} meses")
        if available_informe:
            months_str = ', '.join([f"{m[1]:02d}" for m in available_informe])
            print(f"      Meses: {months_str}")

        available_cda = collector.get_available_months('cda', 2024, 2024)
        print(f"\n   ✅ CDA 2024: {len(available_cda)} meses")
        if available_cda:
            months_str = ', '.join([f"{m[1]:02d}" for m in available_cda])
            print(f"      Meses: {months_str}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # 6. Resumo final
    print("\n" + "="*60)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("="*60)

    # Contar arquivos baixados
    csv_files = list(config.RAW_DATA_DIR.glob("*.csv"))
    print(f"\n📁 Arquivos em {config.RAW_DATA_DIR.name}/:")
    if csv_files:
        for f in sorted(csv_files):
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"   - {f.name} ({size_mb:.2f} MB)")
    else:
        print("   (nenhum arquivo)")

    print("\n" + "="*60)
    if len(csv_files) >= 3:  # cadastro + informe + cda
        print("✅ VALIDAÇÃO CONCLUÍDA COM SUCESSO!")
        print("\n📋 Próximos passos:")
        print("   1. Execute o notebook: 01_data_collection.ipynb")
        print("   2. Baixe dados para período completo")
        print("   3. Continue com análise de fundos REAG")
    else:
        print("⚠️  VALIDAÇÃO INCOMPLETA")
        print("\n🔧 Alguns downloads falharam.")
        print("   Verifique os erros acima e tente novamente.")
    print("="*60)


if __name__ == '__main__':
    main()
