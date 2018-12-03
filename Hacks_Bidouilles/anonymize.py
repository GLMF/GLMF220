#!/home/tristan/.pyenv/shims/python3.7

from Calendar import Calendar

if __name__ == '__main__':
    Calendar.anonymizeCalendar(application_name='Anonymization', source_name='Test', target_name='Activites', share=['location'], generic_summary='RDV', verbose=True)
