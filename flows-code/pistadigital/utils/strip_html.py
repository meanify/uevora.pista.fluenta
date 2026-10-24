import re

tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
    
def remove_html(value):
    """
    Remove HTML tags from a string.
    :param value: The string to clean.
    """
    return tag_re.sub('', value).strip() if isinstance(value, str) else value
    
def strip_html(answers):
    """
    Remove HTML tags from all string entries in a DataFrame.
    :param answers: The DataFrame to clean.
    """
    return answers.map(remove_html)
