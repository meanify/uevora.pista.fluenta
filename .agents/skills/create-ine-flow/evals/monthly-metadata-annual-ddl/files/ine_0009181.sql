CREATE TABLE public.ine_0009181 (
    nuts_ii bpchar(64) NOT NULL,
    tipo_alojamento bpchar(64) NOT NULL,
    ano int4 NOT NULL,
    hospedes float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009181_pkey PRIMARY KEY (nuts_ii, tipo_alojamento, ano)
);
