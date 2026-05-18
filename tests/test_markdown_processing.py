from page_content_api.browser.markdown_processing import html_fragment_to_markdown


def test_html_fragment_to_markdown_strips_links():
    html = "<main><p>Go to <a href='https://example.com'>Example</a></p></main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=False, include_media=True)
    assert "Example" in markdown
    assert "](" not in markdown


def test_html_fragment_to_markdown_media_placeholders():
    html = "<main><img alt='Logo'/><video></video><audio></audio></main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=False)
    assert "[Image: Logo]" in markdown
    assert "[Video]" in markdown
    assert "[Audio]" in markdown


def test_html_fragment_to_markdown_truncates():
    html = "<main>" + ("A" * 50) + "</main>"
    markdown = html_fragment_to_markdown(html, max_chars=10, include_links=True, include_media=True)
    assert markdown.startswith("A")
    assert markdown.endswith("...\n")


def test_html_fragment_to_markdown_keeps_links_when_enabled():
    html = "<main><p><a href='https://example.com'>Example</a></p></main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=True)
    assert "](https://example.com)" in markdown


def test_html_fragment_to_markdown_media_kept_when_enabled():
    html = "<main><img alt='Logo'/><video></video><audio></audio></main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=True)
    assert "[Image" not in markdown
    assert "[Video" not in markdown
    assert "[Audio" not in markdown


def test_html_fragment_to_markdown_media_no_alt():
    html = "<main><img/></main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=False)
    assert "[Image]" in markdown


def test_html_fragment_to_markdown_removes_script_style_noscript_svg_canvas():
    html = """
    <body>
      <script>bad()</script>
      <style>.x{}</style>
      <noscript>nope</noscript>
      <svg><circle></circle></svg>
      <canvas></canvas>
      <main><p>Keep me</p></main>
    </body>
    """
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=True)
    assert "Keep me" in markdown
    assert "bad" not in markdown
    assert "nope" not in markdown


def test_html_fragment_to_markdown_falls_back_to_article_then_body():
    html = "<article><p>Article text</p></article>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=True)
    assert "Article text" in markdown

    html_body = "<body><p>Body text</p></body>"
    markdown_body = html_fragment_to_markdown(html_body, max_chars=1000, include_links=True, include_media=True)
    assert "Body text" in markdown_body


def test_html_fragment_to_markdown_no_truncation_when_under_limit():
    html = "<main>Short text</main>"
    markdown = html_fragment_to_markdown(html, max_chars=1000, include_links=True, include_media=True)
    assert markdown.endswith("Short text")


def test_html_fragment_to_markdown_truncation_above_limit():
    html = "<main>" + ("A" * 50) + "</main>"
    markdown = html_fragment_to_markdown(html, max_chars=10, include_links=True, include_media=True)
    assert markdown.startswith("A")
    assert markdown.endswith("...\n")
