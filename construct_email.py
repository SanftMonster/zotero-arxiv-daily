from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import datetime
import time
from loguru import logger

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  </table>
  """
  return block_template

def highlight_prestigious(names: list[str], prestigious_names: list[str]) -> str:
    """
    Highlight prestigious names in red.
    
    Args:
        names: List of all names
        prestigious_names: List of prestigious names to highlight
        
    Returns:
        HTML string with highlighted names
    """
    # Create a case-insensitive mapping
    prestigious_set = {name.lower() for name in prestigious_names}
    
    result = []
    for name in names:
        if name.lower() in prestigious_set:
            result.append(f'<span style="color: #c0392b; font-weight: bold;">{name}</span>')
        else:
            result.append(name)
    
    return ', '.join(result)


def get_block_html(title:str, authors:str, rate:str,arxiv_id:str, abstract:str, pdf_url:str, code_url:str=None, affiliations:str=None, detailed_summary:str=None, prestigious_institutions:list=None, prestigious_authors:list=None, relevance_score:float=None, institution_score:float=None, author_score:float=None):
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>' if code_url else ''
    
    # Highlight prestigious institutions
    if affiliations and prestigious_institutions:
        # Parse affiliations string and highlight
        affiliation_list = [a.strip() for a in affiliations.split(',')]
        affiliations = highlight_prestigious(affiliation_list, prestigious_institutions)
    
    # Add prestige badges
    prestige_badges = []
    if prestigious_institutions:
        prestige_badges.append('🏛️ <span style="color: #c0392b; font-weight: bold;">顶尖机构</span>')
    if prestigious_authors:
        prestige_badges.append('⭐ <span style="color: #e67e22; font-weight: bold;">知名学者</span>')
    
    prestige_badge_html = ''
    if prestige_badges:
        prestige_badge_html = f"""
    <tr>
        <td style="padding: 4px 0;">
            <div style="font-size: 13px;">
                {' | '.join(prestige_badges)}
            </div>
        </td>
    </tr>"""
    
    # Format score breakdown (optional, for transparency)
    score_breakdown = ''
    if relevance_score is not None and institution_score is not None and author_score is not None:
        score_breakdown = f"""
    <tr>
        <td style="font-size: 12px; color: #7f8c8d; padding: 4px 0;">
            <details>
                <summary style="cursor: pointer;">评分详情</summary>
                <div style="padding: 4px 0; margin-top: 4px;">
                    相关性: {relevance_score:.2f} | 机构声誉: {institution_score:.1f}/100 | 作者影响力: {author_score:.1f}/100
                </div>
            </details>
        </td>
    </tr>"""
    
    # Format detailed summary section if provided
    detailed_summary_section = ''
    if detailed_summary:
        detailed_summary_section = """
    <tr>
        <td style="padding: 12px 0;">
            <div style="background-color: #fff; border-left: 4px solid #5bc0de; padding: 12px 16px; margin: 8px 0; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 16px; font-weight: bold; color: #2c3e50; margin-bottom: 8px;">📝 详细总结</div>
                <div style="font-size: 14px; color: #34495e; line-height: 1.8; text-align: justify; white-space: pre-wrap;">{detailed_summary}</div>
            </div>
        </td>
    </tr>"""
    
    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            <br>
            <i>{affiliations}</i>
        </td>
    </tr>
    {prestige_badge_html}
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {rate}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>arXiv ID:</strong> <a href="https://arxiv.org/abs/{arxiv_id}" target="_blank">{arxiv_id}</a>
        </td>
    </tr>
    {score_breakdown}
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>TLDR:</strong> {abstract}
        </td>
    </tr>
    {detailed_summary_section}
    <tr>
        <td style="padding: 8px 0;">
            <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">PDF</a>
            {code}
        </td>
    </tr>
</table>
"""
    return block_template.format(
        title=title, 
        authors=authors, 
        rate=rate, 
        arxiv_id=arxiv_id, 
        abstract=abstract, 
        pdf_url=pdf_url, 
        code=code, 
        affiliations=affiliations,
        prestige_badge_html=prestige_badge_html,
        score_breakdown=score_breakdown,
        detailed_summary_section=detailed_summary_section.format(detailed_summary=detailed_summary) if detailed_summary else ''
    )

def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(papers:list[ArxivPaper]):
    parts = []
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html())
    
    for p in tqdm(papers,desc='Rendering Email'):
        rate = get_stars(p.score)
        author_list = [a.name for a in p.authors]
        num_authors = len(author_list)
        
        if num_authors <= 5:
            authors = ', '.join(author_list)
        else:
            authors = ', '.join(author_list[:3] + ['...'] + author_list[-2:])
        if p.affiliations is not None:
            affiliations = p.affiliations[:5]
            affiliations = ', '.join(affiliations)
            if len(p.affiliations) > 5:
                affiliations += ', ...'
        else:
            affiliations = 'Unknown Affiliation'
        
        # Generate detailed summary
        logger.info(f"Generating detailed summary for {p.arxiv_id}...")
        detailed_summary = p.detailed_summary
        
        # Get prestigious institutions and authors for highlighting
        prestigious_institutions = p.prestigious_institutions if hasattr(p, 'prestigious_institutions') else []
        prestigious_authors = p.prestigious_authors if hasattr(p, 'prestigious_authors') else []
        
        # Highlight prestigious authors in the author list
        if prestigious_authors:
            author_list_highlighted = []
            for author in author_list:
                if author in [a.name for a in p.authors if a.name in prestigious_authors]:
                    author_list_highlighted.append(f'<span style="color: #e67e22; font-weight: bold;">{author}</span>')
                else:
                    author_list_highlighted.append(author)
            
            if num_authors <= 5:
                authors = ', '.join(author_list_highlighted)
            else:
                # Keep the first 3 and last 2 with highlighting
                authors = ', '.join(author_list_highlighted[:3] + ['...'] + author_list_highlighted[-2:])
        
        parts.append(get_block_html(
            title=p.title,
            authors=authors,
            rate=rate,
            arxiv_id=p.arxiv_id,
            abstract=p.tldr,
            pdf_url=p.pdf_url,
            code_url=p.code_url,
            affiliations=affiliations,
            detailed_summary=detailed_summary,
            prestigious_institutions=prestigious_institutions,
            prestigious_authors=prestigious_authors,
            relevance_score=p.relevance_score if hasattr(p, 'relevance_score') else None,
            institution_score=p.institution_score if hasattr(p, 'institution_score') else None,
            author_score=p.author_score if hasattr(p, 'author_score') else None
        ))
        time.sleep(10)

    content = '<br>' + '</br><br>'.join(parts) + '</br>'
    return framework.replace('__CONTENT__', content)

def send_email(sender:str, receiver:str, password:str,smtp_server:str,smtp_port:int, html:str,):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('Github Action <%s>' % sender)
    msg['To'] = _format_addr('You <%s>' % receiver)
    today = datetime.datetime.now().strftime('%Y/%m/%d')
    msg['Subject'] = Header(f'Daily arXiv {today}', 'utf-8').encode()

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    except Exception as e:
        logger.warning(f"Failed to use TLS. {e}")
        logger.warning(f"Try to use SSL.")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    server.login(sender, password)
    server.sendmail(sender, [receiver], msg.as_string())
    server.quit()
