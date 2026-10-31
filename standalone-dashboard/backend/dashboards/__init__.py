"""One module per dashboard; each exposes ROUTE (the /api/ name) and route()."""

from .. import queries
from . import barometro, noites_quartos, numeros, oportunidades, pulso, radar, raio_x

MODULES = (pulso, raio_x, radar, oportunidades, numeros, barometro, noites_quartos)

ROUTES = {"meta": lambda frames, params: queries.meta(frames)}
ROUTES.update({module.ROUTE: module.route for module in MODULES})
