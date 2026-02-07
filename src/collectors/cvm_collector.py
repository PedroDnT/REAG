import logging

import requests
import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import date, datetime
from tqdm import tqdm
import zipfile
import time
from config.settings import Config

logger = logging.getLogger(__name__)


class CVMCollector:
    """Coletor de dados da CVM (Informe Diário, CDA, Cadastro)"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._ensure_directories()

    def _ensure_directories(self):
        """Garante que diretórios de dados existam"""
        self.config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def check_file_exists(self, url: str) -> bool:
        """
        Verifica se arquivo existe na CVM usando HEAD request

        Args:
            url: URL do arquivo a verificar

        Returns:
            True se arquivo existe (HTTP 200), False caso contrário
        """
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao verificar {url}: {e}")
            return False

    def get_available_months(self, data_type: str = 'informe_diario',
                            start_year: int = 2021,
                            end_year: int = 2026) -> List[Tuple[int, int]]:
        """
        Lista meses disponíveis na CVM para um tipo de dado

        Args:
            data_type: 'informe_diario' ou 'cda'
            start_year: Ano inicial para verificar
            end_year: Ano final para verificar

        Returns:
            Lista de tuplas (year, month) disponíveis
        """
        if start_year > end_year:
            raise ValueError(f"start_year ({start_year}) must be <= end_year ({end_year})")

        available = []
        current_date = datetime.now()

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                # Não verificar meses futuros
                if year * 12 + month > current_date.year * 12 + current_date.month:
                    break

                if data_type == 'informe_diario':
                    url = self.get_informe_diario_url(year, month)
                elif data_type == 'cda':
                    url = self.get_cda_url(year, month)
                else:
                    continue

                if self.check_file_exists(url):
                    available.append((year, month))

        return available

    def get_informe_diario_url(self, year: int, month: int) -> str:
        """Retorna URL do Informe Diário para ano/mês específico (ZIP)"""
        return f"{self.config.CVM_INFORME_DIARIO_URL}/inf_diario_fi_{year}{month:02d}.zip"

    def get_cda_url(self, year: int, month: int) -> str:
        """Retorna URL do CDA para ano/mês específico (ZIP)"""
        return f"{self.config.CVM_CDA_URL}/cda_fi_{year}{month:02d}.zip"

    def get_cadastro_url(self, year: int, month: int) -> str:
        """Retorna URL do Cadastro para ano/mês específico"""
        return f"{self.config.CVM_CADASTRO_URL}/cad_fi_{year}{month:02d}.csv"

    def download_file(self, url: str, output_path: Path, max_retries: int = 4) -> bool:
        """
        Baixa arquivo da URL e salva localmente com retry logic

        Args:
            url: URL do arquivo
            output_path: Caminho de saída
            max_retries: Número máximo de tentativas (padrão: 4)

        Returns:
            True se sucesso, False caso contrário
        """
        for attempt in range(max_retries):
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

            except requests.exceptions.HTTPError as e:
                # Erros 4xx (cliente) não devem ter retry
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Erro HTTP {e.response.status_code}: {url}")
                    return False

                # Erros 5xx (servidor) podem ter retry
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s
                    logger.warning(f"Erro no download (tentativa {attempt + 1}/{max_retries}). "
                                 f"Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Falha apos {max_retries} tentativas: {url}")
                    return False

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Erro: {e}. Tentando novamente em {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Erro ao baixar {url}: {e}")
                    return False

        return False

    def extract_zip(self, zip_path: Path, extract_to: Optional[Path] = None) -> Optional[Path]:
        """Extrai arquivo ZIP e retorna caminho do CSV extraído"""
        try:
            if extract_to is None:
                extract_to = zip_path.parent

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Lista arquivos no ZIP
                file_list = zip_ref.namelist()
                csv_files = [f for f in file_list if f.endswith('.csv')]

                if not csv_files:
                    logger.warning(f"Nenhum arquivo CSV encontrado em {zip_path}")
                    return None

                # Extrai o CSV (assume que há apenas um CSV por ZIP)
                csv_filename = csv_files[0]
                zip_ref.extract(csv_filename, extract_to)

                extracted_path = extract_to / csv_filename
                logger.info(f"Extraido: {extracted_path}")
                return extracted_path

        except Exception as e:
            logger.error(f"Erro ao extrair {zip_path}: {e}")
            return None

    def download_informe_diario(self, year: int, month: int) -> Optional[Path]:
        """Baixa e extrai Informe Diário para ano/mês específico"""
        url = self.get_informe_diario_url(year, month)
        csv_filename = f"inf_diario_fi_{year}{month:02d}.csv"
        csv_path = self.config.RAW_DATA_DIR / csv_filename

        # Verifica se CSV já existe
        if csv_path.exists():
            logger.info(f"Arquivo ja existe: {csv_path}")
            return csv_path

        # Download do ZIP
        zip_filename = f"inf_diario_fi_{year}{month:02d}.zip"
        zip_path = self.config.RAW_DATA_DIR / zip_filename

        if not zip_path.exists():
            success = self.download_file(url, zip_path)
            if not success:
                return None

        # Extrai ZIP
        extracted_path = self.extract_zip(zip_path)

        # Remove ZIP após extração bem-sucedida
        if extracted_path and zip_path.exists():
            zip_path.unlink()

        return extracted_path

    def download_cda(self, year: int, month: int) -> Optional[Path]:
        """Baixa e extrai CDA para ano/mês específico"""
        url = self.get_cda_url(year, month)
        csv_filename = f"cda_fi_{year}{month:02d}.csv"
        csv_path = self.config.RAW_DATA_DIR / csv_filename

        # Verifica se CSV já existe
        if csv_path.exists():
            logger.info(f"Arquivo ja existe: {csv_path}")
            return csv_path

        # Download do ZIP
        zip_filename = f"cda_fi_{year}{month:02d}.zip"
        zip_path = self.config.RAW_DATA_DIR / zip_filename

        if not zip_path.exists():
            success = self.download_file(url, zip_path)
            if not success:
                return None

        # Extrai ZIP
        extracted_path = self.extract_zip(zip_path)

        # Remove ZIP após extração bem-sucedida
        if extracted_path and zip_path.exists():
            zip_path.unlink()

        return extracted_path

    def download_cadastro(self, use_current: bool = True) -> Optional[Path]:
        """
        Baixa Cadastro de Fundos

        Args:
            use_current: Se True, baixa arquivo atual (cad_fi.csv)
                         Se False, baixa histórico completo (cad_fi_hist.zip)

        Nota: Cadastro NÃO é mensal - é um arquivo único atualizado regularmente
        """
        if use_current:
            url = f"{self.config.CVM_CADASTRO_URL}/cad_fi.csv"
            filename = "cad_fi.csv"
        else:
            url = f"{self.config.CVM_CADASTRO_URL}/cad_fi_hist.zip"
            filename = "cad_fi_hist.zip"

        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            logger.info(f"Arquivo ja existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)

        # Se for ZIP, extrair
        if success and filename.endswith('.zip'):
            extracted_path = self.extract_zip(output_path)
            if extracted_path and output_path.exists():
                output_path.unlink()  # Remove ZIP após extração
            return extracted_path

        return output_path if success else None

    def download_period(self, start_year: int, start_month: int,
                       end_year: int, end_month: int,
                       data_types: List[str] = ['informe_diario', 'cda', 'cadastro'],
                       check_availability: bool = True):
        """
        Baixa dados para um período completo

        Args:
            start_year, start_month: Período inicial
            end_year, end_month: Período final
            data_types: Tipos de dados para baixar
            check_availability: Se True, verifica disponibilidade antes de baixar
        """
        if start_year > end_year or (start_year == end_year and start_month > end_month):
            raise ValueError(
                f"Start ({start_year}-{start_month:02d}) must be before "
                f"end ({end_year}-{end_month:02d})"
            )

        results = []

        # Baixar Cadastro (arquivo único, não mensal)
        if 'cadastro' in data_types:
            logger.info("=== Baixando Cadastro (arquivo unico) ===")
            path = self.download_cadastro(use_current=True)
            if path:
                results.append(('cadastro', None, None, path))

        # Para dados mensais (Informe Diário e CDA)
        current_year = start_year
        current_month = start_month

        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            logger.info(f"=== Baixando dados de {current_year}-{current_month:02d} ===")

            if 'informe_diario' in data_types:
                # Verificar disponibilidade
                url = self.get_informe_diario_url(current_year, current_month)
                if check_availability and not self.check_file_exists(url):
                    logger.warning(f"Arquivo nao disponivel: inf_diario_fi_{current_year}{current_month:02d}.zip")
                else:
                    path = self.download_informe_diario(current_year, current_month)
                    if path:
                        results.append(('informe_diario', current_year, current_month, path))

            if 'cda' in data_types:
                # CDA só disponível a partir de 2023-01
                if current_year >= 2023:
                    url = self.get_cda_url(current_year, current_month)
                    if check_availability and not self.check_file_exists(url):
                        logger.warning(f"Arquivo nao disponivel: cda_fi_{current_year}{current_month:02d}.zip")
                    else:
                        path = self.download_cda(current_year, current_month)
                        if path:
                            results.append(('cda', current_year, current_month, path))
                else:
                    logger.warning(f"CDA nao disponivel antes de 2023 (atual: {current_year}-{current_month:02d})")

            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return results
