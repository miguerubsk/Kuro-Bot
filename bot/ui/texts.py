"""Textos compuestos (los que juntan frases de Kuro con datos de la petición)."""

import re

from ..core.text import e, fmt_date


class Texts:
    def __init__(self, kuro):
        self.k = kuro

    def _say(self, key, to, **kw):
        return self.k.persona.say(key, to, **kw)

    def help(self, chat_id: int) -> str:
        """/ayuda: presentación, cómo funciona cada cosa, el trato y los comandos (cada bloque, un párrafo)."""
        say = self.k.persona.to(chat_id)
        tracking = self.k.tracker.enabled
        if self.k.is_admin(chat_id):
            clients = ["/descargados — lo que ha pedido cada uno",
                       "/resetcupo [código] — devolver los cupos (de uno o de todos)"]
            if self.k.access.can_add:
                clients.append("/alta código [nombre] — dejar pasar a alguien por su código de cliente")
            commands = ["/pedir nombre — buscar un anime", "/pendientes — encargos por decidir"]
            if tracking:
                commands.append("/seguimientos — todo lo que se vigila cada semana")
            commands += ["/id — número de este chat", "/ayuda — esta ayuda"]
            blocks = [say("help_intro_boss"), say("help_how_boss")]
            if tracking:
                blocks.append(say("help_track_boss"))
            blocks += [say("help_rules_head") + "\n" + say("help_admin"),
                       say("help_clients_head") + "\n" + "\n".join(clients),
                       say("help_commands_head") + "\n" + "\n".join(commands)]
            return "\n\n".join(blocks)

        commands = ["/pedir nombre — buscar un anime", "/cupo — cuántos encargos te quedan esta semana"]
        if tracking:
            commands.append("/seguimientos — lo que te vigilo cada semana (y dejar de seguirlo)")
        commands += ["/id — tu código de cliente", "/ayuda — esta ayuda"]
        blocks = [say("help_intro_client"), say("help_how")]
        if tracking:
            blocks.append(say("help_track", limit=self.k.tracker.limit))
        blocks += [say("help_rules_head") + "\n" + say("help_user", limit=self.k.quota.limit),
                   say("help_commands_head") + "\n" + "\n".join(commands)]
        return "\n\n".join(blocks)

    def no_quota(self, chat_id: int) -> str:
        nxt = self.k.quota.next_slot(chat_id)
        when = self._say("no_quota_when", chat_id, date=fmt_date(nxt)) if nxt else ""
        return self._say("no_quota", chat_id, limit=self.k.quota.limit, when_html=when)

    def airing_note(self, to: int, airing: bool, label: str) -> str:
        if not airing:
            return ""
        m = re.search(r"\[(\d+/[^\]]+)\]", label or "")
        return "\n\n" + self._say("airing", to, progress=f" ({m.group(1)})" if m else "")

    @staticmethod
    def post_label(post) -> str:
        return f" ({'🎬 ' if post.movie else ''}{post.label})" if post.label else (" (🎬)" if post.movie else "")

    def admin_request(self, req) -> str:
        label = f" — {e(req.label)}" if req.label else ""
        kind = "película" if req.movie else ("en emisión" if req.airing else "serie")
        return (self._say("admin_request", self.k.admin, who=req.user_name, req_id=req.id)
                + f"\n<b>{e(req.title)}</b>{label}\nTipo: {kind}\n{e(req.post_url)}\n{e(req.paste_url)}")

    def admin_bundle(self, reqs, notes: dict, seasons: dict) -> str:
        first = reqs[0]
        lines = [self._say("admin_bundle_request", self.k.admin, who=first.user_name, bundle=first.bundle_id)]
        for r in reqs:
            label = f" — {e(r.label)}" if r.label else ""
            t = seasons.get(r.id)
            lines.append(f"\n<b>{'T' + e(t) + ' · ' if t else ''}{e(r.title)}</b>{label} (#{r.id})\n"
                         f"{e(r.post_url)}{notes.get(r.id, '')}")
        return "\n".join(lines)
