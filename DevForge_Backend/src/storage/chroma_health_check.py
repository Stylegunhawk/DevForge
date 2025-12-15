    
    async def health_check(self) -> bool:
        """
        Check if ChromaDB backend is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to get collection info
            def _check_sync():
                count = self._collection.count()
                return count >= 0  # Any valid count means healthy
            
            result = await asyncio.to_thread(_check_sync)
            return result
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False
