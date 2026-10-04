"""Mem0 factories use the shared offline embedder and the existing provider seam.

Imported only after engine.bootstrap has disabled Mem0 telemetry and default paths.
"""
import asyncio
from contextvars import ContextVar
import json
import math

from mem0.embeddings.base import EmbeddingBase
from mem0.llms.base import LLMBase

from renulus.contracts import ApiError

embedding_binding = ContextVar('renulus_memory_embedding')
generation_binding = ContextVar('renulus_memory_generation')


class OfflineEmbedding:
    def __init__(self, config):
        self.config, self.model = config, None
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(config['tokenizer_path']))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def embed_batch(self, texts, memory_action='add'):
        # Do not quietly truncate facts or queries at the 512-token helper limit.
        if any(len(self.tokenizer.encode(text).ids) > self.config['max_tokens'] for text in texts):
            raise ApiError('memory_embedding_budget', 'Shorten this learning note or query before indexing', 422)
        if self.model is None:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(model_name=self.config['model_id'],
                specific_model_path=str(self.config['model_path']),
                cache_dir=str(self.config['cache_dir']), local_files_only=True,
                threads=self.config['cpu_threads'], providers=['CPUExecutionProvider'], cuda=False)
        values = self.model.query_embed(texts) if memory_action == 'search' else self.model.passage_embed(texts)
        vectors = [[float(x) for x in vector] for vector in values]
        if len(vectors) != len(texts) or any(len(v) != self.config['dimensions'] or
                not all(math.isfinite(x) for x in v) for v in vectors):
            raise ApiError('memory_invalid_embedding', 'The offline embedding helper returned incompatible vectors', 503)
        return vectors

    def embed(self, text, memory_action='add'):
        return self.embed_batch([text], memory_action)[0]


class RegisteredEmbedding(EmbeddingBase):
    def __init__(self, config=None):
        super().__init__(config)
        self.delegate = embedding_binding.get()

    def embed(self, text, memory_action='add'):
        return self.delegate.embed(text, memory_action)

    def embed_batch(self, texts, memory_action='add'):
        return self.delegate.embed_batch(texts, memory_action)


class ApprovedLLM(LLMBase):
    def generate_response(self, messages, response_format=None, tools=None, tool_choice='auto', **kwargs):
        if tools:
            raise ApiError('memory_tools_disabled', 'Memory extraction does not use agent tools', 409)
        try:
            binding = generation_binding.get()
        except LookupError:
            raise ApiError('memory_generation_not_scoped', 'Memory extraction needs the approved scoped provider', 503) from None
        if not binding['current']():
            raise ApiError('memory_capture_cancelled', 'Memory capture was cancelled or superseded', 409)

        async def generate():
            provider = binding['services'].get('provider')
            system = '\n\n'.join(message['content'] for message in messages if message['role'] == 'system')
            output = ''
            # The provider selects only the approved subscription/model, with no fallback.
            async for delta in provider.stream(
                    [message for message in messages if message['role'] != 'system'],
                    scope=binding['scope'], run_id=binding['run_id'], system=system,
                    purpose='memory-extraction'):
                if not binding['current']():
                    raise ApiError('memory_capture_cancelled', 'Memory capture was cancelled or superseded', 409)
                output += delta
                if len(output) > 16000:
                    raise ApiError('memory_extraction_invalid', 'Memory extraction exceeded its response budget', 502)
            try:
                result = json.loads(output)
                records = result['memory']
                if not isinstance(records, list) or len(records) > 12 or any(
                        not isinstance(row, dict) or not isinstance(row.get('text'), str) or
                        not row['text'].strip() or len(row['text']) > 2000 for row in records):
                    raise ValueError()
            except (ValueError, TypeError, KeyError):
                raise ApiError('memory_extraction_invalid', 'The selected provider did not return usable learning facts', 502, True) from None
            return json.dumps({'memory': [{'text': row['text']} for row in records]})

        future = asyncio.run_coroutine_threadsafe(generate(), binding['loop'])
        try:
            return future.result(timeout=120)
        except TimeoutError:
            future.cancel()
            raise ApiError('memory_extraction_timeout', 'Memory extraction timed out. Retry the capture', 503, True) from None
