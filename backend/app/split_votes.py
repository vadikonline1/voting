"""One-time repair of votes made before "one vote per property": a vote that covers several properties is
split into one vote per property. The first property keeps the original vote; every other property gets
its own owner record, vote (same answers and signature), receipt PDF and property row.

It is safe to run again: a vote that already has one property is left alone. Emails already sent are not
sent again."""
import json
import os

from . import models
from .ballot_template import load_template
from .config import settings
from .pdf import generate_receipt_pdf


def _property_address(vp_rows, prop: dict, default: str) -> str:
    for row in vp_rows:
        if row.tip_proprietate == prop["tip_proprietate"] and row.nr_proprietate == prop["nr_proprietate"] \
                and (row.bloc or "") == (prop.get("bloc") or ""):
            return row.adresa or default
    return default


def _receipt(db, election, token, vote) -> None:
    path = os.path.join(settings.data_dir, "receipts", f"{token.id}.pdf")
    generate_receipt_pdf(
        election=election,
        voter=token,
        answers=json.loads(vote.answers_json or "{}"),
        submitted_at=vote.submitted_at or token.voted_at,
        signature_path=vote.signature_path,
        output_path=path,
        gdpr_consent_at=vote.gdpr_consent_at,
        template=load_template(db),
    )
    vote.receipt_pdf_path = path


def split_multi_property_votes(db) -> int:
    """Returns how many votes were split."""
    candidates = db.query(models.VoterToken).filter(models.VoterToken.vote.has()).all()
    split = 0
    for token in candidates:
        props = token.properties
        if len(props) <= 1:
            continue
        vote = token.vote
        election = token.election
        vp_rows = db.query(models.VoterProperty).filter(models.VoterProperty.token_id == token.id).all()
        default_address = token.adresa or ""

        # the first property stays on the original vote
        first = props[0]
        first_address = _property_address(vp_rows, first, default_address)
        first_bloc = first.get("bloc") or ""
        token.tip_proprietate = first["tip_proprietate"]
        token.nr_proprietate = first["nr_proprietate"]
        token.bloc = first_bloc
        token.adresa = first_address
        token.properties_json = json.dumps(
            [{"tip_proprietate": first["tip_proprietate"], "nr_proprietate": first["nr_proprietate"],
              "bloc": first_bloc, "adresa": first_address}],
            ensure_ascii=False,
        )
        for row in vp_rows:
            if row.tip_proprietate == first["tip_proprietate"] and row.nr_proprietate == first["nr_proprietate"]:
                row.adresa = first_address
                row.bloc = first_bloc

        new_tokens = []
        for prop in props[1:]:
            address = _property_address(vp_rows, prop, default_address)
            bloc = prop.get("bloc") or ""
            new_token = models.VoterToken(
                election_id=token.election_id,
                nume_prenume=token.nume_prenume,
                phone=token.phone,
                str_locatar=token.str_locatar,
                email=token.email,
                tip_proprietate=prop["tip_proprietate"],
                nr_proprietate=prop["nr_proprietate"],
                properties_json=json.dumps(
                    [{"tip_proprietate": prop["tip_proprietate"], "nr_proprietate": prop["nr_proprietate"],
                      "bloc": bloc, "adresa": address}],
                    ensure_ascii=False,
                ),
                adresa=address,
                bloc=bloc,
                created_at=token.created_at,
                voted_at=token.voted_at,
            )
            db.add(new_token)
            db.flush()
            db.add(models.Vote(
                token_id=new_token.id,
                election_id=token.election_id,
                answers_json=vote.answers_json,
                signature_path=vote.signature_path,
                gdpr_consent_at=vote.gdpr_consent_at,
                submitted_at=vote.submitted_at,
                ip_address=vote.ip_address,
                email_sent=vote.email_sent,
            ))
            for row in vp_rows:
                if row.tip_proprietate == prop["tip_proprietate"] and row.nr_proprietate == prop["nr_proprietate"]:
                    row.token_id = new_token.id
                    row.adresa = address
                    row.bloc = bloc
            new_tokens.append(new_token)
        db.commit()

        # every ballot gets its own PDF (the old one still lists all the properties)
        _receipt(db, election, token, vote)
        for new_token in new_tokens:
            _receipt(db, election, new_token, new_token.vote)
        db.commit()
        split += 1
    return split
