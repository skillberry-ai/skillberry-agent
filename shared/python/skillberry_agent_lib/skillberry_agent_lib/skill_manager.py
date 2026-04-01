import os
import logging
from typing import Optional, List

from skillberry_agent_lib.skillberry_store import skillberry_store

logger = logging.getLogger(__name__)


def _extract_search_term_from_chat_history(chat_history: List) -> Optional[str]:
    """
    Extract a search term from chat history for skill discovery.
    
    Args:
        chat_history: List of chat messages
        
    Returns:
        str: Extracted search term
        None: If no suitable term found
    """
    # TODO: Implement intelligent search term extraction from chat history
    # For now, return a default search term
    return "airline"


def resolve_skill_uuid(
    skill_uuid: Optional[str] = None,
    skill_name: Optional[str] = None,
    chat_history: Optional[List] = None
) -> Optional[str]:
    """
    Resolve skill UUID using multiple strategies.
    
    Resolution priority:
    1. Direct UUID (if provided)
    2. Skill name lookup (if provided)
    3. Search-based resolution using chat history (runtime/production mode)
    
    Args:
        skill_uuid: Direct skill UUID (highest priority)
        skill_name: Skill name to resolve to UUID (medium priority)
        chat_history: List of chat messages for search-based resolution (runtime/production mode)
        
    Returns:
        str: Resolved skill UUID
        None: If no skill could be resolved
    """
    # Priority 1: Direct UUID
    if skill_uuid:
        logger.info(f"[resolve_skill_uuid] Using provided UUID: {skill_uuid}")
        return skill_uuid

    # Priority 2: Skill name lookup
    if skill_name:
        logger.info(f"[resolve_skill_uuid] Resolving UUID from name: {skill_name}")
        try:
            skill = skillberry_store.get_skill(skill_name)
            resolved_uuid = skill.get('uuid')
            if resolved_uuid:
                logger.info(f"[resolve_skill_uuid] Resolved '{skill_name}' to UUID: {resolved_uuid}")
                return resolved_uuid
            logger.error(f"[resolve_skill_uuid] Skill '{skill_name}' found but has no UUID")
        except Exception as e:
            logger.error(f"[resolve_skill_uuid] Failed to resolve skill name '{skill_name}': {e}")
        return None
    
    # Priority 3: Search-based resolution using chat history
    if chat_history:
        logger.info("[resolve_skill_uuid] Attempting search-based resolution from chat history")
        try:
            search_term = _extract_search_term_from_chat_history(chat_history)
            if not search_term:
                logger.warning("[resolve_skill_uuid] Could not extract search term from chat history")
                return None
                
            logger.info(f"[resolve_skill_uuid] Extracted search term: '{search_term}'")
            resolved_uuid = skillberry_store.find_skill_uuid_by_search(search_term)
            
            if resolved_uuid:
                logger.info(f"[resolve_skill_uuid] Found skill via search: {resolved_uuid}")
                return resolved_uuid
            logger.warning(f"[resolve_skill_uuid] No skill found for search term: '{search_term}'")
        except Exception as e:
            logger.warning(f"[resolve_skill_uuid] Search-based resolution failed: {e}")
    
    # No skill resolved
    logger.info("[resolve_skill_uuid] No skill resolved - will create VMCP without skill")
    return None


# Made with Bob