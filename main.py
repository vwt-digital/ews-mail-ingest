import config
import requests

from requests.auth import HTTPBasicAuth

url = "https://autodiscover.hierinloggen.nl/ews/exchange.asmx"

headers = {'content-type': 'text/xml'}
body = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
    <soap:Header>
        <t:RequestServerVersion Version="Exchange2007_SP1" />
    </soap:Header>
    <soap:Body>
        <FindItem xmlns="http://schemas.microsoft.com/exchange/services/2006/messages"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
              Traversal="Shallow">
            <ItemShape>
                <t:BaseShape>IdOnly</t:BaseShape>
            </ItemShape>
            <ParentFolderIds>
                <t:DistinguishedFolderId Id="inbox"/>
            </ParentFolderIds>
        </FindItem>
    </soap:Body>
</soap:Envelope>"""

response = requests.post(url, data=body, headers=headers,
                         auth=HTTPBasicAuth(config.EXCHANGE_USERNAME,
                                            config.EXCHANGE_PASSWORD))

print(response.content)
