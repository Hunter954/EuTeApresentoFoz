import os
import threading, time
from pathlib import Path
from sqlalchemy import inspect, text
from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv

from .config import Config
from .models import db, User, AdSlot, SiteSetting, Category, Product, CityPhoto, BeforeAfter, WhatsAppGroup, ChatMessage
from .routes import site_bp
from .admin import admin_bp
from .wp_client import WPClient
from .sync import sync_categories, sync_posts

login_manager = LoginManager()
login_manager.login_view = "admin.login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _ensure_schema_updates():
    inspector = inspect(db.engine)

    if inspector.has_table("user"):
        user_columns = {col["name"] for col in inspector.get_columns("user")}
        user_statements = []
        if "is_active" not in user_columns:
            user_statements.append('ALTER TABLE "user" ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE')
        if "created_at" not in user_columns:
            user_statements.append('ALTER TABLE "user" ADD COLUMN created_at TIMESTAMP')
        if "updated_at" not in user_columns:
            user_statements.append('ALTER TABLE "user" ADD COLUMN updated_at TIMESTAMP')
        if user_statements:
            with db.engine.begin() as conn:
                for stmt in user_statements:
                    conn.execute(text(stmt))
                conn.execute(text('UPDATE "user" SET is_active = TRUE WHERE is_active IS NULL'))
                conn.execute(text('UPDATE "user" SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL'))
                conn.execute(text('UPDATE "user" SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'))

    if inspector.has_table("guide_listing"):
        guide_columns = {col["name"] for col in inspector.get_columns("guide_listing")}
        guide_statements = []
        if "source_provider" not in guide_columns:
            guide_statements.append('ALTER TABLE guide_listing ADD COLUMN source_provider VARCHAR(60)')
        if "source_ref" not in guide_columns:
            guide_statements.append('ALTER TABLE guide_listing ADD COLUMN source_ref VARCHAR(190)')
        if "source_query" not in guide_columns:
            guide_statements.append('ALTER TABLE guide_listing ADD COLUMN source_query VARCHAR(220)')
        if "maps_url" not in guide_columns:
            guide_statements.append('ALTER TABLE guide_listing ADD COLUMN maps_url VARCHAR(1000)')
        if "last_imported_at" not in guide_columns:
            guide_statements.append('ALTER TABLE guide_listing ADD COLUMN last_imported_at TIMESTAMP')
        if guide_statements:
            with db.engine.begin() as conn:
                for stmt in guide_statements:
                    conn.execute(text(stmt))


def _ensure_defaults():
    defaults = [
        ("header_top", "Publicidade (Topo - faixa)"),
        ("home_top", "Publicidade (Home - faixa no meio)"),
        ("home_mid", "Publicidade (Final da matéria)"),
        ("home_bottom", "Publicidade (Home - faixa inferior)"),
        ("sidebar_1", "Publicidade (Sidebar 1)"),
        ("sidebar_2", "Publicidade (Sidebar 2)"),
    ]
    for key, name in defaults:
        if not AdSlot.query.filter_by(key=key).first():
            db.session.add(AdSlot(key=key, name=name, html="", is_active=True))

    for key, value in [
        ("live_embed_html", ""),
        ("logo_url", ""),
        ("site_name", os.getenv("SITE_NAME", "Eu Te Apresento Foz")),
        ("favicon_url", ""),
        ("default_share_image", ""),
        ("site_tagline", "Histórias, notícias e memórias de Foz do Iguaçu"),
        ("default_meta_description", "Eu Te Apresento Foz reúne notícias, histórias, memórias, fotos da cidade, grupos locais, bate-papo e uma lojinha nostálgica de Foz do Iguaçu."),
        ("facebook_app_id", ""),
        ("google_site_verification", ""),
        ("google_analytics_id", ""),
        ("contact_email", ""),
        ("contact_phone", ""),
        ("instagram_url", ""),
        ("facebook_url", ""),
        ("youtube_url", ""),
        ("x_url", ""),
        ("footer_contact_label", "Fale conosco"),
        ("footer_contact_url", "#"),
        ("footer_privacy_label", "Privacidade"),
        ("footer_privacy_url", "#"),
        ("footer_terms_label", "Termos e Condições"),
        ("footer_terms_url", "#"),
        ("footer_social_label", "Redes Sociais:"),
        ("footer_copyright_text", "© 2026 Eu Te Apresento Foz. Todos os direitos reservados."),
        ("site_keywords", "Foz do Iguaçu, notícias de Foz, histórias da cidade, fotos antigas, antes e depois, grupos WhatsApp, turismo, memória local"),
        ("top_menu_category_ids", "[]"),
        ("weather_text", "24°C Parcialmente nublado"),
        ("announcement_url", "#"),
        ("contact_address", "Centro - Foz do Iguaçu/PR"),
        ("newsletter_placeholder", "Seu melhor e-mail"),
        ("hub_enabled", "0"),
        ("hub_site_key", ""),
        ("hub_receive_token", ""),
        ("hub_auto_push", "1"),
        ("hub_remote_sites_json", "[]"),
    ]:
        if not SiteSetting.query.filter_by(key=key).first():
            db.session.add(SiteSetting(key=key, value=value))

    if not Category.query.filter_by(slug="noticias").first():
        db.session.add(Category(name="Notícias", slug="noticias"))
    if not Category.query.filter_by(slug="materias").first():
        db.session.add(Category(name="Matérias", slug="materias"))
    if not Category.query.filter_by(slug="historias").first():
        db.session.add(Category(name="Histórias", slug="historias"))

    if not Product.query.first():
        demo_products = [
            Product(name="Caneca da Cidade", slug="caneca-da-cidade", price_label="R$ 34,90", description="Caneca nostálgica com arte inspirada em Foz.", sort_order=1),
            Product(name="Camiseta Raízes", slug="camiseta-raizes", price_label="R$ 59,90", description="Camiseta para quem carrega a cidade no peito.", sort_order=2),
            Product(name="Pôster Antigo", slug="poster-antigo", price_label="R$ 29,90", description="Pôster decorativo com memória local.", sort_order=3),
            Product(name="Chaveiro Estação", slug="chaveiro-estacao", price_label="R$ 19,90", description="Lembrança simples e afetiva da cidade.", sort_order=4),
        ]
        db.session.add_all(demo_products)

    if not CityPhoto.query.first():
        db.session.add_all([
            CityPhoto(title="Catedral e praça", caption="Um olhar afetivo sobre os cartões-postais da cidade.", sort_order=1),
            CityPhoto(title="Fim de tarde no rio", caption="Paisagens que contam a rotina de Foz.", sort_order=2),
            CityPhoto(title="A cidade vista de cima", caption="Foz em perspectiva, memórias em movimento.", sort_order=3),
        ])

    if not BeforeAfter.query.first():
        db.session.add_all([
            BeforeAfter(title="Praça Central", location="Centro", year_before="1988", year_after="Hoje", sort_order=1),
            BeforeAfter(title="Rua do Comércio", location="Centro", year_before="1995", year_after="Hoje", sort_order=2),
            BeforeAfter(title="Estação Ferroviária", location="Região histórica", year_before="1970", year_after="Hoje", sort_order=3),
        ])

    if not WhatsAppGroup.query.first():
        db.session.add_all([
            WhatsAppGroup(name="Empregos", description="Vagas e oportunidades de trabalho na cidade.", member_count="1.842 membros", icon_class="bi-people-fill", sort_order=1),
            WhatsAppGroup(name="Comércio Local", description="Divulgue seu negócio e compre do bairro.", member_count="2.315 membros", icon_class="bi-shop-window", sort_order=2),
            WhatsAppGroup(name="Eventos", description="Fique por dentro dos eventos da cidade.", member_count="1.673 membros", icon_class="bi-calendar-event", sort_order=3),
            WhatsAppGroup(name="Memórias da Cidade", description="Compartilhe fotos e histórias antigas.", member_count="912 membros", icon_class="bi-camera", sort_order=4),
        ])

    if not ChatMessage.query.first():
        db.session.add_all([
            ChatMessage(name="Maria do Carmo", message="Alguém lembra do Cine Guarani? Quantas sessões inesquecíveis!", is_approved=True),
            ChatMessage(name="João Batista", message="Lembro sim! Meu primeiro filme foi lá. Que época!", is_approved=True),
            ChatMessage(name="Lúcia Helena", message="Sábado vai ter feira de adoção na Praça Central. Vamos participar?", is_approved=True),
        ])

    db.session.commit()


def _auto_sync_loop(app: Flask):
    with app.app_context():
        client = WPClient(app.config["WP_BASE_URL"])
        while True:
            try:
                sync_categories(client)
                sync_posts(client, max_pages=50, per_page=app.config["WP_PER_PAGE"])
            except Exception:
                pass
            time.sleep(app.config["AUTO_SYNC_INTERVAL"])


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)

    Path(app.config["MEDIA_ROOT"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(site_bp)
    app.register_blueprint(admin_bp)

    from datetime import datetime
    app.jinja_env.globals["now"] = datetime.now

    with app.app_context():
        db.create_all()
        _ensure_schema_updates()
        _ensure_defaults()

        admin_email = "admin@admin.com"
        admin_password = "senha123"

        u = User.query.filter_by(email=admin_email).first()
        if not u:
            u = User(email=admin_email, is_admin=True, is_active=True)
            u.set_password(admin_password)
            db.session.add(u)
        else:
            u.is_admin = True
            u.is_active = True
            if not u.password_hash:
                u.set_password(admin_password)
        db.session.commit()
        print("ADMIN OK:", admin_email)

    if app.config.get("AUTO_SYNC_INTERVAL", 0) and app.config["AUTO_SYNC_INTERVAL"] > 0:
        t = threading.Thread(target=_auto_sync_loop, args=(app,), daemon=True)
        t.start()

    return app
