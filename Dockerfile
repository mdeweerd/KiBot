FROM ghcr.io/inti-cmnb/kicad6_auto:1.4.0-8_k6.0.9_d11.5
LABEL AUTHOR Salvador E. Tropea <stropea@inti.gob.ar>
LABEL Description="Export various files from KiCad projects (KiCad 6)"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /mnt

ENTRYPOINT [ "/entrypoint.sh" ]
