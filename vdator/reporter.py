from enum import Enum

class Reporter():
  """
  Keep track of types of responses
  """

  class ReportType(Enum):
    CORRECT = 'correct'
    WARNING = 'warning'
    ERROR = 'error'
    INFO = 'info'

  def __init__(self):
    self.report = {
      'correct': 0,
      'warning': 0,
      'error': 0,
      'info': 0
    }

  def print_report(self, type, message, record=True):
    """    
    Parameters
    ----------
    type : ReportType
      type of report: 'correct', 'warning', 'error', or 'info' 
      
    message : str
      reply message

    record : bool
      should this report be kept track of in total 
    """
    if record:
      self.report[type.lower()] += 1
    return "[" + type.upper() + "] " + message
    
  def get_report(self):
    """
    Get the report results
      
    Returns
    -------
    report dict: {'correct' : int, 'warning' : int, 'error' : int, 'info' : int}
    """
    return self.report
    
  def display_report(self):
    """
    Get the report reply
      
    Returns
    -------
    str reply
    """
    reply = str(self.report['correct']) + " correct, "
    
    reply += str(self.report['warning']) + " warning"
    reply += "" if self.report['warning'] == 1 else "s"
    
    reply += ", " + str(self.report['error']) + " error"
    reply += "" if self.report['error'] == 1 else "s"
    
    reply += ", and " + str(self.report['info']) + " info"
    return reply
