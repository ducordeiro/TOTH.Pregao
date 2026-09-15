"""Read-only DOCX page-part package for Block 2's HTML replica."""
import base64
import copy
import io
import zipfile
from functools import lru_cache
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def template_page_parts_preview(path):
    path = Path(path).resolve()
    stat = path.stat()
    return dict(_cached_preview(str(path), stat.st_mtime_ns, stat.st_size))


@lru_cache(maxsize=8)
def _cached_preview(path, modified_ns, size):
    document = Document(path)
    section = document.sections[-1]
    references = {}
    for current in document.sections:
        for tag in ("headerReference", "footerReference"):
            for reference in current._sectPr.findall(qn("w:" + tag)):
                references[(tag, reference.get(qn("w:type")))] = copy.deepcopy(reference)
    even_odd = document.settings.odd_and_even_pages_header_footer
    title_page = section.different_first_page_header_footer
    padding = {"top": 0, "right": 5.4, "bottom": 0, "left": 5.4}
    for style in document.styles.element.findall(qn("w:style")):
        if style.get(qn("w:type")) == "table" and style.get(qn("w:default")) == "1":
            margins = style.find(qn("w:tblPr") + "/" + qn("w:tblCellMar"))
            if margins is not None:
                for side, key in (("top", "top"), ("left", "left"), ("start", "left"), ("bottom", "bottom"), ("right", "right"), ("end", "right")):
                    value = margins.find(qn("w:" + side))
                    if value is not None and value.get(qn("w:type"), "dxa") == "dxa":
                        padding[key] = int(value.get(qn("w:w"), "0")) / 20
    properties = copy.deepcopy(section._sectPr)
    for tag in ("headerReference", "footerReference"):
        for reference in list(properties.findall(qn("w:" + tag))):
            properties.remove(reference)
    for (tag, kind), reference in references.items():
        if kind == "even" and not even_odd:
            continue
        properties.insert(0, reference)
    body = document._element.body
    for element in list(body):
        body.remove(element)
    # Three pages expose the first, even and default page parts without rendering
    # the proposal body, OCR or a PDF. Source package parts remain untouched.
    for index in range(3):
        paragraph = OxmlElement("w:p")
        run = OxmlElement("w:r")
        if index:
            line_break = OxmlElement("w:br")
            line_break.set(qn("w:type"), "page")
            run.append(line_break)
        text = OxmlElement("w:t")
        text.text = " "
        run.append(text)
        paragraph.append(run)
        body.append(paragraph)
    body.append(properties)
    output = io.BytesIO()
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            target.writestr(entry, document.part.blob if entry.filename == "word/document.xml" else source.read(entry))
    return {
        "docx_base64": base64.b64encode(output.getvalue()).decode("ascii"),
        "content_width_pt": (section.page_width - section.left_margin - section.right_margin) / 12700,
        "default_cell_padding_pt": padding,
        "page_width_pt": section.page_width.pt,
        "page_height_pt": section.page_height.pt,
        "left_margin_pt": section.left_margin.pt,
        "right_margin_pt": section.right_margin.pt,
        "header_distance_pt": section.header_distance.pt,
        "footer_distance_pt": section.footer_distance.pt,
        "first_header_blank": bool(title_page and ("headerReference", "first") not in references),
        "first_footer_blank": bool(title_page and ("footerReference", "first") not in references),
        "even_header_blank": bool(even_odd and ("headerReference", "even") not in references),
        "even_footer_blank": bool(even_odd and ("footerReference", "even") not in references),
    }
