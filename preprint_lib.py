import requests
from datetime import date
from dateutil.relativedelta import relativedelta
import time

def get_date_range():
    today = date.today()
    one_month_ago = today - relativedelta(weeks=1)
    return f"{one_month_ago.strftime('%Y-%m-%d')}/{today.strftime('%Y-%m-%d')}"

def doi2url(doi: str) -> str:
    if doi.startswith("http://") or doi.startswith("https://"):
        return doi
    return f"https://doi.org/{doi}"


def get_latest_preprints():
    interval = get_date_range()
    cursor = 0
    format = 'json'
    data_continue = True
    data_all = list()
    while data_continue:
        url = f"https://api.biorxiv.org/details/biorxiv/{interval}/{cursor}/{format}"
        response = requests.get(url)
        data = response.json()
        data_all.extend(data['collection'])
        if len(data['collection'])==0:
            data_continue = False
        else:
            cursor += len(data['collection'])
            time.sleep(0.2)

    neuro_only = list(filter(lambda x: x['category']=='neuroscience',data_all) )
    for i in range(len(neuro_only)):
        neuro_only[i]['doi'] = doi2url(neuro_only[i]['doi'])
    return neuro_only


if __name__ == '__main__':
    neuro_only = get_latest_preprints()
    print(neuro_only)


