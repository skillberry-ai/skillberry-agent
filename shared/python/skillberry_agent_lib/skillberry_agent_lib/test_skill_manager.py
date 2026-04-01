"""
Unit tests for skill_manager module.

Tests the resolve_skill_uuid function which resolves skill UUIDs using multiple strategies:
1. Direct UUID (highest priority)
2. Skill name lookup (medium priority)
3. Search-based resolution using chat history (lowest priority)
"""

import unittest
from unittest.mock import patch
from skillberry_agent_lib.skill_manager import resolve_skill_uuid, _extract_search_term_from_chat_history


class TestExtractSearchTerm(unittest.TestCase):
    """Test the _extract_search_term_from_chat_history helper function."""
    
    def test_extract_search_term_returns_default(self):
        """Test that extract_search_term returns default 'airline' term."""
        chat_history = [
            {"role": "user", "content": "I need to book a flight"},
            {"role": "assistant", "content": "I can help with that"}
        ]
        result = _extract_search_term_from_chat_history(chat_history)
        self.assertEqual(result, "airline")
    
    def test_extract_search_term_with_empty_history(self):
        """Test extract_search_term with empty chat history."""
        result = _extract_search_term_from_chat_history([])
        self.assertEqual(result, "airline")
    
    def test_extract_search_term_with_none(self):
        """Test extract_search_term with None input."""
        result = _extract_search_term_from_chat_history(None)
        self.assertEqual(result, "airline")


class TestResolveSkillUuidDirectUuid(unittest.TestCase):
    """Test resolve_skill_uuid with direct UUID (Priority 1)."""
    
    def test_direct_uuid_provided(self):
        """Test that direct UUID is returned without any API calls."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = resolve_skill_uuid(skill_uuid=test_uuid)
        self.assertEqual(result, test_uuid)
    
    def test_direct_uuid_takes_precedence_over_name(self):
        """Test that direct UUID takes precedence over skill name."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = resolve_skill_uuid(skill_uuid=test_uuid, skill_name="some-skill")
        self.assertEqual(result, test_uuid)
    
    def test_direct_uuid_takes_precedence_over_chat_history(self):
        """Test that direct UUID takes precedence over chat history."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        chat_history = [{"role": "user", "content": "test"}]
        result = resolve_skill_uuid(skill_uuid=test_uuid, chat_history=chat_history)
        self.assertEqual(result, test_uuid)


class TestResolveSkillUuidByName(unittest.TestCase):
    """Test resolve_skill_uuid with skill name lookup (Priority 2)."""
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_store')
    def test_skill_name_resolution_success(self, mock_api):
        """Test successful skill name resolution."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        mock_api.get_skill.return_value = {
            "name": "test-skill",
            "uuid": test_uuid,
            "description": "Test skill"
        }
        
        result = resolve_skill_uuid(skill_name="test-skill")
        
        self.assertEqual(result, test_uuid)
        mock_api.get_skill.assert_called_once_with("test-skill")
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_store')
    def test_skill_name_resolution_no_uuid(self, mock_api):
        """Test skill name resolution when skill has no UUID."""
        mock_api.get_skill.return_value = {
            "name": "test-skill",
            "description": "Test skill"
            # No uuid field
        }
        
        result = resolve_skill_uuid(skill_name="test-skill")
        
        self.assertIsNone(result)
        mock_api.get_skill.assert_called_once_with("test-skill")
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_store')
    def test_skill_name_resolution_api_error(self, mock_api):
        """Test skill name resolution when API call fails."""
        mock_api.get_skill.side_effect = Exception("API Error")
        
        result = resolve_skill_uuid(skill_name="test-skill")
        
        self.assertIsNone(result)
        mock_api.get_skill.assert_called_once_with("test-skill")
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_store')
    def test_skill_name_takes_precedence_over_chat_history(self, mock_api):
        """Test that skill name takes precedence over chat history."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        mock_api.get_skill.return_value = {"uuid": test_uuid}
        chat_history = [{"role": "user", "content": "test"}]
        
        result = resolve_skill_uuid(skill_name="test-skill", chat_history=chat_history)
        
        self.assertEqual(result, test_uuid)
        mock_api.get_skill.assert_called_once_with("test-skill")
        # Should not call search methods
        mock_api.find_skill_uuid_by_search.assert_not_called()


class TestResolveSkillUuidBySearch(unittest.TestCase):
    """Test resolve_skill_uuid with search-based resolution (Priority 3)."""
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_store')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_search_based_resolution_success(self, mock_extract, mock_api):
        """Test successful search-based resolution."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        mock_extract.return_value = "airline"
        mock_api.find_skill_uuid_by_search.return_value = test_uuid
        
        chat_history = [{"role": "user", "content": "Book a flight"}]
        result = resolve_skill_uuid(chat_history=chat_history)
        
        self.assertEqual(result, test_uuid)
        mock_extract.assert_called_once_with(chat_history)
        mock_api.find_skill_uuid_by_search.assert_called_once_with("airline")
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_api')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_search_based_resolution_no_search_term(self, mock_extract, mock_api):
        """Test search-based resolution when no search term can be extracted."""
        mock_extract.return_value = None
        
        chat_history = [{"role": "user", "content": "test"}]
        result = resolve_skill_uuid(chat_history=chat_history)
        
        self.assertIsNone(result)
        mock_extract.assert_called_once_with(chat_history)
        mock_api.find_skill_uuid_by_search.assert_not_called()
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_api')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_search_based_resolution_no_skill_found(self, mock_extract, mock_api):
        """Test search-based resolution when no skill is found."""
        mock_extract.return_value = "airline"
        mock_api.find_skill_uuid_by_search.return_value = None
        
        chat_history = [{"role": "user", "content": "test"}]
        result = resolve_skill_uuid(chat_history=chat_history)
        
        self.assertIsNone(result)
        mock_extract.assert_called_once_with(chat_history)
        mock_api.find_skill_uuid_by_search.assert_called_once_with("airline")
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_api')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_search_based_resolution_api_error(self, mock_extract, mock_api):
        """Test search-based resolution when API call fails."""
        mock_extract.return_value = "airline"
        mock_api.find_skill_uuid_by_search.side_effect = Exception("API Error")
        
        chat_history = [{"role": "user", "content": "test"}]
        result = resolve_skill_uuid(chat_history=chat_history)
        
        self.assertIsNone(result)
        mock_extract.assert_called_once_with(chat_history)
        mock_api.find_skill_uuid_by_search.assert_called_once_with("airline")


class TestResolveSkillUuidNoInput(unittest.TestCase):
    """Test resolve_skill_uuid with no input parameters."""
    
    def test_no_parameters_returns_none(self):
        """Test that no parameters returns None."""
        result = resolve_skill_uuid()
        self.assertIsNone(result)
    
    def test_empty_skill_name_returns_none(self):
        """Test that empty skill name returns None."""
        result = resolve_skill_uuid(skill_name="")
        self.assertIsNone(result)
    
    def test_empty_chat_history_returns_none(self):
        """Test that empty chat history returns None."""
        result = resolve_skill_uuid(chat_history=[])
        self.assertIsNone(result)


class TestResolveSkillUuidPriorityOrder(unittest.TestCase):
    """Test the priority order of resolution strategies."""
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_api')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_all_three_strategies_uuid_wins(self, mock_extract, mock_api):
        """Test that direct UUID wins when all three strategies are provided."""
        direct_uuid = "direct-uuid-111"
        name_uuid = "name-uuid-222"
        search_uuid = "search-uuid-333"
        
        mock_api.get_skill.return_value = {"uuid": name_uuid}
        mock_extract.return_value = "airline"
        mock_api.find_skill_uuid_by_search.return_value = search_uuid
        
        result = resolve_skill_uuid(
            skill_uuid=direct_uuid,
            skill_name="test-skill",
            chat_history=[{"role": "user", "content": "test"}]
        )
        
        self.assertEqual(result, direct_uuid)
        # Should not call any API methods
        mock_api.get_skill.assert_not_called()
        mock_extract.assert_not_called()
        mock_api.find_skill_uuid_by_search.assert_not_called()
    
    @patch('skillberry_agent_lib.skill_manager.skillberry_api')
    @patch('skillberry_agent_lib.skill_manager._extract_search_term_from_chat_history')
    def test_name_and_search_name_wins(self, mock_extract, mock_api):
        """Test that skill name wins over search when both are provided."""
        name_uuid = "name-uuid-222"
        search_uuid = "search-uuid-333"
        
        mock_api.get_skill.return_value = {"uuid": name_uuid}
        mock_extract.return_value = "airline"
        mock_api.find_skill_uuid_by_search.return_value = search_uuid
        
        result = resolve_skill_uuid(
            skill_name="test-skill",
            chat_history=[{"role": "user", "content": "test"}]
        )
        
        self.assertEqual(result, name_uuid)
        mock_api.get_skill.assert_called_once_with("test-skill")
        # Should not call search methods
        mock_extract.assert_not_called()
        mock_api.find_skill_uuid_by_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()


# Made with Bob