import aiohttp
import logging

logger = logging.getLogger(__name__)

class VisualexApiClient:
    """
    Un client semplice per interagire con la tua VisualexAPI.
    """
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 300):
        self.base_url = base_url
        self.fetch_url = f"{self.base_url}/fetch_all_data"
        self.timeout = timeout  # Default 5 minutes for range requests

    async def get_data_for_article(self, article_id: str) -> dict:
        """
        Recupera i dati per un articolo.
        Per ora, gestisce solo i codici, ma possiamo estenderlo.
        """
        # TODO: Migliorare questo parsing per gestire tutti i tipi di 'act_type'
        payload = {}
        if "c.c." in article_id.lower():
            payload = {"act_type": "codice civile", "article": article_id.lower().replace("art. ", "").replace(" c.c.", "")}
        elif "c.p." in article_id.lower():
            payload = {"act_type": "codice penale", "article": article_id.lower().replace("art. ", "").replace(" c.p.", "")}
        else:
            # Un approccio generico per altri tipi di atti, da migliorare
            parts = article_id.split()
            if len(parts) >= 2:
                 payload = {"act_type": "legge", "article": parts[-1]} # Assumiamo 'legge' come default
            else:
                logger.error(f"Formato articolo non riconosciuto: {article_id}")
                return {"error": "Formato articolo non riconosciuto"}

        logger.info(f"Chiamata a VisualexAPI con payload: {payload}")

        async with aiohttp.ClientSession() as session:
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with session.post(self.fetch_url, json=payload, timeout=timeout) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    # L'API sembra restituire una lista, prendiamo il primo elemento.
                    if data and isinstance(data, list):
                        return data[0]
                    
                    logger.warning(f"Formato risposta API non valido: {data}")
                    return {"error": "Risposta API non valida"}

            except aiohttp.ClientError as e:
                logger.error(f"Errore nella chiamata a VisualexAPI: {e}")
                return {"error": str(e)}
    
    async def get_data_for_articles_payload(self, payload: dict) -> dict:
        """
        Recupera i dati per uno o più articoli usando un payload personalizzato.
        L'API gestisce internamente i range (es. "1414-1416") e restituisce tutti
        gli articoli nel range, inclusi bis, ter, quater, etc.
        
        Args:
            payload: Dict con chiavi:
                - act_type: tipo di atto (es. "codice civile")
                - article: numero articolo o range (es. "1414" o "1414-1416")
                - act_number: numero atto (opzionale, per leggi/decreti)
                - date: data atto (opzionale)
        
        Returns:
            Lista di dict, uno per ogni articolo trovato dall'API
        """
        logger.info(f"Chiamata a VisualexAPI con payload: {payload}")

        async with aiohttp.ClientSession() as session:
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with session.post(self.fetch_url, json=payload, timeout=timeout) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    # L'API restituisce una lista di articoli
                    if data and isinstance(data, list):
                        logger.info(f"API returned {len(data)} articles")
                        return data
                    
                    logger.warning(f"Formato risposta API non valido: {data}")
                    return {"error": "Risposta API non valida"}

            except aiohttp.ClientError as e:
                logger.error(f"Errore nella chiamata a VisualexAPI: {e}")
                return {"error": str(e)}