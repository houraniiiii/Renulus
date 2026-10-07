"""Invented article/keys, shaped like the observed primary API contracts."""
PMCID = "PMC10001"
PMID = "10001"


def europe(row=None, **changes):
    item = {"id": PMID, "source": "MED", "pmid": PMID, "pmcid": PMCID,
            "title": "Synthetic kidney article", "authorString": "Synthetic Author",
            "doi": "10.0000/synthetic", "firstPublicationDate": "2026-09-01",
            "isOpenAccess": "Y", "license": "cc by", "pubTypeList": {"pubType": ["Journal Article"]}}
    item.update(changes)
    return {"hitCount": 1, "resultList": {"result": [item if row is None else row]}}


def article(*, licence="https://creativecommons.org/licenses/by/4.0/", pmcid=PMCID, statement="", body="", attributes="", article_type="research-article"):
    return f'''<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="{article_type}">
      <front><journal-meta><publisher><publisher-name>Synthetic Press</publisher-name></publisher></journal-meta>
      <article-meta><article-id pub-id-type="pmcid">{pmcid}</article-id>
      <article-id pub-id-type="pmid">{PMID}</article-id><article-id pub-id-type="doi">10.0000/synthetic</article-id>
      <title-group><article-title>Synthetic kidney article</article-title></title-group>
      <contrib-group><contrib contrib-type="author"><name><surname>Author</surname><given-names>Synthetic</given-names></name></contrib></contrib-group>
      <pub-date pub-type="epub"><year>2026</year><month>9</month><day>1</day></pub-date>
      <permissions><copyright-statement>Copyright Synthetic Author 2026</copyright-statement>
      <copyright-year>2026</copyright-year><copyright-holder>Synthetic Author</copyright-holder>
      <license {attributes}><license-p>{statement}<ext-link xlink:href="{licence}">CC licence</ext-link></license-p></license></permissions>
      <abstract><p>Synthetic metadata study.</p></abstract></article-meta></front>
      <body><sec><title>Results</title><p>Kidney study paragraph with <italic>synthetic</italic> observations.</p>{body}</sec></body>
      </article>'''.encode()
