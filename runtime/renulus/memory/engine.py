"""Hermes OSSBackend operations over real Mem0, embedded Qdrant and FastEmbed.

The upstream constructor drops history_db_path and recreates changed dimensions.
Replace only that configuration step; retain its add/search/update/delete methods.
Never initialise its platform backend or unrestricted turn-sync plugin.
"""
from contextlib import contextmanager
import importlib.util
import logging
import os
from pathlib import Path
import sys
import threading

from renulus.contracts import ApiError

_import_lock = threading.RLock()


def bootstrap(services):
    with _import_lock:
        root = services.paths.owned('state/memory-engine-bootstrap')
        root.mkdir(parents=True, exist_ok=True)
        # These are public engine settings, never credentials. Import-time defaults
        # must be constrained even though every active database path is explicit.
        previous = {key: os.environ.get(key) for key in ('MEM0_DIR', 'MEM0_TELEMETRY')}
        os.environ['MEM0_DIR'], os.environ['MEM0_TELEMETRY'] = str(root), 'false'
        try:
            import mem0
            from mem0.memory import main, telemetry
            from mem0.utils import spacy_models
            telemetry.MEM0_TELEMETRY = main.MEM0_TELEMETRY = False
            # Mem0 2.2.1 otherwise tries to download an unselected spaCy model.
            # Its built-in original-text/no-entity fallbacks are sufficient here.
            spacy_models._load_failed_full = spacy_models._load_failed_lemma = True
            for name in list(logging.Logger.manager.loggerDict):
                if name == 'mem0' or name.startswith(('mem0.', 'posthog')):
                    logging.getLogger(name).disabled = True
            return mem0
        except ImportError:
            raise ApiError('memory_package_missing', 'The selected Mem0 helpers are not installed', 503, True) from None
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def embedding_config(services):
    helpers = services.registry.get('helpers')
    if helpers is None or not hasattr(helpers, 'embedding_config'):
        raise ApiError('helper_assets_missing', 'Validated offline embedding helpers are not available', 503, True)
    config = helpers.embedding_config()
    if (config['model_id'] != 'BAAI/bge-small-en-v1.5' or config['dimensions'] != 384 or
            config['max_tokens'] != 512 or config['local_files_only'] is not True or
            config['cpu_threads'] != 2 or not config.get('fingerprint')):
        raise ApiError('memory_embedding_incompatible', 'The memory index needs a coordinated helper rebuild', 503)
    for key in ('model_path', 'tokenizer_path'):
        if not Path(config[key]).resolve().is_relative_to(services.paths.helpers.resolve()):
            raise ApiError('memory_helper_path', 'Memory embedding assets must be app owned', 503)
    if not Path(config['cache_dir']).resolve().is_relative_to(services.paths.cache.resolve()):
        raise ApiError('memory_helper_path', 'The embedding cache must be app owned', 503)
    return config


def hermes_backend(services):
    source = services.paths.source_root / 'upstream/hermes/plugins/memory/mem0/_backend.py'
    if not source.is_file():
        raise ApiError('memory_hermes_missing', 'The attributed Hermes Mem0 adapter is missing', 503)
    name = 'renulus.memory._vendored_hermes_backend'
    with _import_lock:
        loaded = sys.modules.get(name)
        if loaded is not None:
            if Path(loaded.__file__).resolve() != source.resolve():
                raise ApiError('memory_hermes_conflict', 'Another Hermes memory adapter is loaded', 503)
            return loaded.OSSBackend
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[name] = module
        return module.OSSBackend


class Mem0Index:
    collection = 'renulus_learner_facts'
    user_id, agent_id = 'local-learner', 'renulus-learning'

    def __init__(self, services, path, embedding, *, transient=False):
        self.path = Path(path).resolve()
        boundary = (services.paths.indexes / 'learner-memory').resolve()
        if self.path == boundary or not self.path.is_relative_to(boundary):
            raise ApiError('memory_index_path', 'The memory index must belong to its isolated profile', 503)
        if not transient:
            self.path.mkdir(parents=True, exist_ok=True)
        mem0 = bootstrap(services)
        from mem0.configs.base import MemoryConfig
        from mem0.utils.factory import EmbedderFactory, LlmFactory
        from .providers import embedding_binding
        # As in Hermes's registered LLM provider, validate supported config and
        # then select our app-owned factory. No OpenAI client/default is created.
        LlmFactory.register_provider('renulus_subscription', 'renulus.memory.providers.ApprovedLLM')
        EmbedderFactory.provider_to_class['renulus_offline'] = 'renulus.memory.providers.RegisteredEmbedding'
        vector_config = {'path': str(self.path / 'qdrant'), 'collection_name': self.collection,
                         'embedding_model_dims': 384, 'on_disk': True}
        if transient:
            from qdrant_client import QdrantClient
            vector_config = {'client': QdrantClient(location=':memory:'),
                'collection_name': self.collection, 'embedding_model_dims': 384, 'on_disk': False}
        config = MemoryConfig(
            history_db_path=':memory:' if transient else str(self.path / 'history.sqlite3'), version='v1.1',
            vector_store={'provider': 'qdrant', 'config': vector_config},
            embedder={'provider': 'fastembed', 'config': {'model': embedding.config['model_id'],
                                                        'embedding_dims': 384}},
            llm={'provider': 'openai', 'config': {}},
            custom_instructions='Retain only general educational learning points. Exclude all case facts, '
                'patient information and clinical instructions. Do not infer competence from a discussion.')
        config.llm.provider, config.embedder.provider = 'renulus_subscription', 'renulus_offline'
        upstream = hermes_backend(services)

        class ProfileBackend(upstream):
            def __init__(backend, memory_config):
                backend._memory = mem0.Memory(memory_config)

        token = embedding_binding.set(embedding)
        try:
            self.backend = ProfileBackend(config)
        finally:
            embedding_binding.reset(token)
        self.memory = self.backend._memory
        # Do not initialise Mem0's optional BM25 helper or any extra NLP model.
        self.memory.vector_store._bm25_encoder = False
        self.memory.db.connection.execute('PRAGMA secure_delete=ON')

    def add(self, record):
        response = self.backend.add([{'role': 'user', 'content': record['text']}],
            user_id=self.user_id, agent_id=self.agent_id, infer=False,
            metadata={'canonical_id': record['id'], 'canonical_revision': record['revision'],
                      'scope': record['scope'], 'topic_id': record['topic_id'], 'kind': record['kind']})
        rows = response.get('results', [])
        if len(rows) != 1 or not rows[0].get('id'):
            raise ApiError('memory_index_failed', 'Mem0 could not index this canonical learning note', 503, True)
        return rows[0]['id']

    def search(self, query, limit):
        return self.backend.search(query, filters={'user_id': self.user_id, 'agent_id': self.agent_id},
                                   top_k=limit, rerank=False)

    @contextmanager
    def generation(self, binding):
        from .providers import generation_binding
        token = generation_binding.set(binding)
        try:
            yield
        finally:
            generation_binding.reset(token)

    def extract(self, text, binding):
        with self.generation(binding):
            response = self.backend.add([{'role': 'user', 'content': text}],
                user_id=self.user_id, agent_id=self.agent_id, infer=True)
        return [row['memory'] for row in response.get('results', []) if row.get('event') == 'ADD']

    def purge_history(self):
        manager = self.memory.db
        with manager._lock:
            conn = manager.connection
            conn.execute('DELETE FROM history')
            conn.execute('DELETE FROM messages')
            conn.commit()
            conn.execute('VACUUM')

    def close(self):
        try:
            self.memory.db.close()
        finally:
            self.backend.close()
