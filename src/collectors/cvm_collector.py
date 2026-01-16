import requests
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import date
from tqdm import tqdm
from config.settings import Config


class CVMCollector:
    """Coletor de dados da CVM (Informe Diário, CDA, Cadastro)"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._ensure_directories()

    def _ensure_directories(self):
        """Garante que diretórios de dados existam"""
        self.config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def get_informe_diario_url(self, year: int, month: int) -> str:
        """Retorna URL do Informe Diário para ano/mês específico"""
        return f"{self.config.CVM_INFORME_DIARIO_URL}/inf_diario_fi_{year}{month:02d}.csv"

    def get_cda_url(self, year: int, month: int) -> str:
        """Retorna URL do CDA para ano/mês específico"""
        return f"{self.config.CVM_CDA_URL}/cda_fi_{year}{month:02d}.csv"

    def get_cadastro_url(self, year: int, month: int) -> str:
        """Retorna URL do Cadastro para ano/mês específico"""
        return f"{self.config.CVM_CADASTRO_URL}/cad_fi_{year}{month:02d}.csv"

    def download_file(self, url: str, output_path: Path) -> bool:
        """Baixa arquivo da URL e salva localmente"""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=output_path.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            return True
        except Exception as e:
            print(f"Erro ao baixar {url}: {e}")
            return False

    def download_informe_diario(self, year: int, month: int) -> Optional[Path]:
        """Baixa Informe Diário para ano/mês específico"""
        url = self.get_informe_diario_url(year, month)
        filename = f"informe_diario_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_cda(self, year: int, month: int) -> Optional[Path]:
        """Baixa CDA para ano/mês específico"""
        url = self.get_cda_url(year, month)
        filename = f"cda_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_cadastro(self, year: int, month: int) -> Optional[Path]:
        """Baixa Cadastro para ano/mês específico"""
        url = self.get_cadastro_url(year, month)
        filename = f"cadastro_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_period(self, start_year: int, start_month: int,
                       end_year: int, end_month: int,
                       data_types: list[str] = ['informe_diario', 'cda', 'cadastro']):
        """Baixa dados para um período completo"""
        results = []

        current_year = start_year
        current_month = start_month

        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            print(f"\n=== Baixando dados de {current_year}-{current_month:02d} ===")

            if 'informe_diario' in data_types:
                path = self.download_informe_diario(current_year, current_month)
                if path:
                    results.append(('informe_diario', current_year, current_month, path))

            if 'cda' in data_types:
                path = self.download_cda(current_year, current_month)
                if path:
                    results.append(('cda', current_year, current_month, path))

            if 'cadastro' in data_types:
                path = self.download_cadastro(current_year, current_month)
                if path:
                    results.append(('cadastro', current_year, current_month, path))

            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return results
