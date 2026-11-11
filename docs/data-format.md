# data-format

## NAME

data-format, the files between the converter and the worker

## FILES

catalog.json
    Hand-edited list of tracked documents, one entry per document.

raw/<id>.<ext>
    The file as downloaded from mevzuat.gov.tr. The extension is pdf, doc, docx, html or txt. A .txt file holds text copied from the mevzuat.gov.tr page, one paragraph per line. Keep one raw file per document. The path stays the same when the document is updated, so git history keeps every earlier version.

data/<id>.json
    Converter output for one document. Never edited by hand.

## ID

An id is lowercase ASCII, the document type and the number joined by a hyphen.

    kanun-6098
    yonetmelik-12345

The types are kanun, khk, cbk (Cumhurbaşkanlığı Kararnamesi), tuzuk, yonetmelik, teblig, karar and genelge.

## CATALOG ENTRY

catalog.json holds an object with one key, documents, which is a list of entries.

| field       | type     | required | meaning |
|-------------|----------|----------|---------|
| id          | string   | yes      | See ID. |
| type        | string   | yes      | One of the types under ID. |
| number      | string   | yes      | Number as printed on mevzuat.gov.tr. |
| title       | string   | yes      | Full title in Turkish, as printed. The converter warns when the document header disagrees. |
| short_names | string[] | no       | Names a user may type, such as TBK. Matching ignores case and Turkish characters. |
| source_url  | string   | yes      | The page of the document on mevzuat.gov.tr. |

## DOCUMENT FILE

data/<id>.json holds one object.

| field                 | type           | meaning |
|-----------------------|----------------|---------|
| id, type, number, title, short_names, source_url | | Copied from catalog.json. |
| accepted_at           | string or null | Kabul tarihi as an ISO date, read from the document header. |
| official_gazette      | object or null | Resmi Gazete date (ISO) and issue number, read from the document header. |
| downloaded_at         | string         | ISO date. When raw/<id>.<ext> last changed in git. This is the upload date, which is normally the download date. |
| latest_amendment_seen | string or null | ISO date. The newest date found in amendment notes. |
| converter_version     | string         | Version of the converter that wrote the file. |
| articles              | Article[]      | In document order. See ARTICLE. |

## ARTICLE

| field    | type           | meaning |
|----------|----------------|---------|
| order    | integer        | Position in the document, starting at 1. |
| kind     | string         | madde, ek_madde, gecici_madde, ek_gecici_madde or mukerrer_madde. |
| number   | string         | As printed, for example 344, 4/A or 1. |
| label    | string         | As printed, for example MADDE 344 or GEÇİCİ MADDE 1. |
| heading  | string or null | Madde başlığı, the heading line above the article. Several heading lines are joined with " / ". |
| path     | string[]       | Section headings above the article, outermost first. |
| repealed | boolean        | True when the article text starts with "(Mülga:". A partial repeal such as "(Mülga birinci fıkra: ...)" does not count. |
| text     | string         | Full article text. Paragraphs are separated by one blank line. Amendment notes stay inline, as printed. |
| notes    | string[]       | Amendment notes found in the text, as printed. |

The worker builds the outline of a document from the path and heading of each article, so there is no separate section list.

## EXAMPLE

Values written as ... are placeholders.

```json
{
  "id": "kanun-6098",
  "type": "kanun",
  "number": "6098",
  "title": "Türk Borçlar Kanunu",
  "short_names": ["TBK"],
  "source_url": "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=6098&MevzuatTur=1&MevzuatTertip=5",
  "accepted_at": "2011-01-11",
  "official_gazette": { "date": "2011-02-04", "number": "27836" },
  "downloaded_at": "2026-11-11",
  "latest_amendment_seen": "...",
  "converter_version": "0.1.0",
  "articles": [
    {
      "order": 1,
      "kind": "madde",
      "number": "1",
      "label": "MADDE 1",
      "heading": "...",
      "path": ["BİRİNCİ KISIM ...", "..."],
      "repealed": false,
      "text": "...",
      "notes": []
    }
  ]
}
```

## NORMALIZATION

Search compares normalized text. The import step normalizes article text and headings, and the worker normalizes queries with the same steps. The reference implementation is converter/mevzuat_converter/normalize.py.

1. Decompose every letter into its base letter and its marks (Unicode NFD), then drop the marks. ş becomes s, İ becomes I, â becomes a.
2. Replace the dotless ı with i, then lowercase.
3. Replace every run of characters outside a to z and 0 to 9 with one space, then trim.

After these steps KİRACI, kiracı and kiraci are the same word. Prefix matching then lets kiracı find kiracının and kiracıya. It does not handle consonant changes such as kitap and kitabı, so Claude retries with the other form when needed.

## KNOWN TEXT PATTERNS

The converter must recognize these forms. The list grows as samples arrive. The separator after an article number is a hyphen, an en dash or an em dash. A few labels have no separator, and then the text after the number starts with a capital letter or a bracket. Soft hyphens are removed from every paragraph before matching.

    MADDE 344 –                           article, new style
    Madde 5-                              article, old style
    MADDE 428 İşyerinin                   article without a dash
    Madde 87 (Mülga: ...)                 article without a dash
    MADDE 4/A-                            inserted article
    GEÇİCİ MADDE 1 –                      provisional article
    EK MADDE 2 –                          additional article
    EK GEÇİCİ MADDE 1 –                   additional provisional article
    Mükerrer Madde 257 –                  duplicate-numbered article in older laws
    (Değişik: 24/11/2016-6763/14 md.)     amendment note in a law
    (Ek:RG-15/5/2019-30775-CK-36/1 md.)   amendment note citing Resmi Gazete
    (Mülga: ...)                          repealed text

## NOT STORED

No user data, no query logs and no secrets. The secret path segment of the MCP URL lives in a Cloudflare secret.

## SEE ALSO

architecture.md
