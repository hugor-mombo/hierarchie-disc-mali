"""Réutiliser les restrictions territoriales existantes sur les sources dérivées."""
from superset import db


def apply_regional_security(datasets):
    from superset.connectors.sqla.models import RowLevelSecurityFilter
    # Le jeu historique de relances couvre l'ensemble des rôles territoriaux.
    rules=[r for r in db.session.query(RowLevelSecurityFilter).all()
           if any(t.id==7 for t in r.tables)]
    if not rules:
        raise RuntimeError('Restrictions de référence introuvables : publication interrompue')
    allowed_roles={role.id:role for rule in rules for role in rule.roles}
    from superset import security_manager
    for name in ['Admin','Alpha']:
        role=security_manager.find_role(name)
        if role is not None:
            allowed_roles[role.id]=role
    for rule in rules:
        attached={t.id for t in rule.tables}
        for dataset in datasets:
            if dataset.id not in attached:
                rule.tables.append(dataset)
    # L'accès à un dashboard ne suffit pas pour obtenir un périmètre national.
    name='DISC_RLS_DERIVED_DEFAULT_DENY'
    base=db.session.query(RowLevelSecurityFilter).filter_by(name=name).one_or_none()
    if base is None:
        kind=type(rules[0].filter_type)
        base_kind=next((v for v in kind if v.value=='Base'),None) if hasattr(kind,'__members__') else 'Base'
        base=RowLevelSecurityFilter(name=name,filter_type=base_kind,clause='1 = 0')
        db.session.add(base)
    base.roles=list(allowed_roles.values())
    attached={t.id for t in base.tables}
    for dataset in datasets:
        if dataset.id not in attached:
            base.tables.append(dataset)
    from district_security import apply_district_security
    apply_district_security(datasets)
    db.session.flush()
    return len(rules)
