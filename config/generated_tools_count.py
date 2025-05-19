import logging


class GeneratedToolsCount:
    """
    This class is used to keep track of the number of generated tools.
    """

    def __init__(self):
        self.generated_tools_count = 0

    def reset_generated_tools_count(self):
        """
        This function resets the generated tools count to 0
        """

        self.generated_tools_count = 0

    def increment_generated_tools_count(self):
        """
        This function increments the generated tools count by 1
        """

        self.generated_tools_count += 1

    def get_generated_tools_count(self):
        """
        This function returns the current generated tools count
        """

        return self.generated_tools_count


generated_tools_count = GeneratedToolsCount()
