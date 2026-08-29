# first line: 114
    @staticmethod
    @memory.cache
    def get_embedding(text, embedding_model):
        """Get embedding for a text with caching"""
        if embedding_model is None:
            logger.error("Embedding model not available")
            return None
        return embedding_model.encode(text)
