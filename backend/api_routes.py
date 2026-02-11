from flask import Blueprint, jsonify
from flask_wtf.csrf import generate_csrf
from models import PageContent
import json

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/csrf-token')
def get_csrf_token():
    token = generate_csrf()
    return jsonify({'csrf_token': token})

@api_bp.route('/page-content/<page_name>')
def get_page_content(page_name):
    contents = PageContent.query.filter_by(page_name=page_name).all()
    result = {}
    for content in contents:
        try:
            result[content.section_name] = json.loads(content.content)
        except json.JSONDecodeError:
            result[content.section_name] = {}
    return jsonify(result)

@api_bp.route('/page-content/<page_name>/<section_name>')
def get_section_content(page_name, section_name):
    content = PageContent.query.filter_by(
        page_name=page_name,
        section_name=section_name
    ).first()
    
    if not content:
        return jsonify({'error': 'Content not found'}), 404
    
    try:
        return jsonify(json.loads(content.content))
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 500

@api_bp.route('/page-html/<page_name>')
def get_page_html(page_name):
    content = PageContent.query.filter_by(
        page_name=page_name,
        section_name='html'
    ).first()

    if content:
        html_val = getattr(content, 'html_content', None) or getattr(content, 'jsx_content', None)
        if html_val:
            return jsonify({'html': html_val})

    return jsonify({'html': None})
