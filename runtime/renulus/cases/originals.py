# SPDX-License-Identifier: MIT
"""Case originals use the existing canonical Save/backup transaction boundary."""
import base64
import binascii
import hashlib

from renulus.contracts import ApiError, durable_id

CHUNK_BYTES = 48 * 1024
MAX_ORIGINALS = 16
MAX_CASE_ORIGINAL_BYTES = 32 * 1024 * 1024
METADATA = ('id', 'filename', 'title', 'media_type', 'bytes', 'sha256')


def accepted_original(filename, title, media_type, data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 10 * 1024 * 1024:
        raise ApiError('case_attachment_limit', 'Choose an original up to 10 MiB', 413)
    return {'id': durable_id('case_attachment'), 'filename': filename, 'title': title,
            'media_type': media_type, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(), 'data': data,
            'saved': False, 'original_available': True}


def check_capacity(attachments, additional):
    if (len(attachments) >= MAX_ORIGINALS or
            sum(a['bytes'] for a in attachments) + additional['bytes'] > MAX_CASE_ORIGINAL_BYTES):
        raise ApiError('case_attachment_limit', 'A case can keep up to 16 originals totalling 32 MiB. Remove an attachment before adding another.', 413)


def load_metadata(db, case_id):
    rows = db.fetch_all(
        'SELECT a.*, COUNT(p.part) AS parts FROM case_attachments a '
        'LEFT JOIN case_attachment_parts p ON p.attachment_id=a.id '
        'WHERE a.case_id=? GROUP BY a.id ORDER BY a.rowid', (case_id,))
    return [{**{key: row[key] for key in METADATA}, 'data': None, 'saved': True,
             'original_available': row['parts'] == (row['bytes'] + CHUNK_BYTES - 1) // CHUNK_BYTES}
            for row in rows]


def read_original(db, attachment):
    data = attachment['data']
    if data is None:
        rows = db.fetch_all('SELECT part,data FROM case_attachment_parts WHERE attachment_id=? ORDER BY part',
                            (attachment['id'],))
        try:
            if len(rows) != (attachment['bytes'] + CHUNK_BYTES - 1) // CHUNK_BYTES:
                raise ValueError
            pieces = []
            for number, row in enumerate(rows):
                if row['part'] != number:
                    raise ValueError
                piece = base64.b64decode(row['data'], validate=True)
                expected = min(CHUNK_BYTES, attachment['bytes'] - number * CHUNK_BYTES)
                if len(piece) != expected:
                    raise ValueError
                pieces.append(piece)
            data = b''.join(pieces)
        except (ValueError, binascii.Error):
            raise ApiError('case_original_unavailable', 'The original is missing or incomplete. Restore a full backup that includes originals.', 409) from None
    if len(data) != attachment['bytes'] or hashlib.sha256(data).hexdigest() != attachment['sha256']:
        raise ApiError('case_original_integrity', 'The saved original does not match its recorded hash', 409)
    return data


def save_originals(conn, case_id, attachments):
    kept = {a['id'] for a in attachments}
    for row in conn.execute('SELECT id FROM case_attachments WHERE case_id=?', (case_id,)):
        if row['id'] not in kept:
            conn.execute('DELETE FROM case_attachments WHERE id=? AND case_id=?', (row['id'], case_id))
    for attachment in attachments:
        if attachment['data'] is None:
            row = conn.execute('SELECT * FROM case_attachments WHERE id=? AND case_id=?',
                               (attachment['id'], case_id)).fetchone()
            if row is None or any(row[key] != attachment[key] for key in METADATA):
                raise ApiError('case_revision_conflict', 'The saved original changed; reopen the case', 409, True)
            continue
        conn.execute('INSERT INTO case_attachments(id,case_id,filename,title,media_type,bytes,sha256) VALUES(?,?,?,?,?,?,?)',
                     (attachment['id'], case_id, *(attachment[key] for key in METADATA[1:])))
        data = attachment['data']
        conn.executemany('INSERT INTO case_attachment_parts VALUES(?,?,?)',
                         ((attachment['id'], number, base64.b64encode(data[offset:offset + CHUNK_BYTES]).decode('ascii'))
                          for number, offset in enumerate(range(0, len(data), CHUNK_BYTES))))
