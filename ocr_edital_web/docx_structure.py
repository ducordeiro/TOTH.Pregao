import hashlib
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
NAMESPACES = {"w": WORD_NAMESPACE}
TEXT_TAG = f"{{{WORD_NAMESPACE}}}t"
XML_SPACE = f"{{{XML_NAMESPACE}}}space"
CONTENT_PART_PATTERN = re.compile(
    r"^word/(?:document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$"
)
GENERATED_TABLE_BLOCK_ID = "generated-proposal-table"


@dataclass(frozen=True)
class MiniBoxSlot:
    id: str
    part: str
    paragraph_index: int
    marker_index: int
    start: int
    end: int
    content: str
    order: int


@dataclass(frozen=True)
class DocxAnalysis:
    signature: str
    nodes: tuple[dict, ...]
    slots: tuple[MiniBoxSlot, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DocumentBlockLayout:
    order: tuple[str, ...]
    mini_box_order: tuple[str, ...]
    table_paragraph_index: int | None


def _document_signature(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _node_id(
    signature: str,
    part: str,
    paragraph_index: int,
    node_type: str,
    node_index: int,
) -> str:
    value = f"{signature}:{part}:{paragraph_index}:{node_type}:{node_index}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _content_part_sort_key(name: str) -> tuple[int, str]:
    priorities = (
        ("word/document.xml", 0),
        ("word/header", 1),
        ("word/footer", 2),
        ("word/footnotes.xml", 3),
        ("word/endnotes.xml", 4),
        ("word/comments.xml", 5),
    )
    for prefix, priority in priorities:
        if name.startswith(prefix):
            return priority, name
    return len(priorities), name


def _root_brace_spans(text: str) -> tuple[list[tuple[int, int]], list[str]]:
    spans: list[tuple[int, int]] = []
    warnings: list[str] = []
    depth = 0
    start = -1
    for index, character in enumerate(text):
        if character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}":
            if depth == 0:
                warnings.append(f"Chave de fechamento sem abertura na posição {index + 1}.")
                continue
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
    if depth:
        warnings.append("Bloco com chave de abertura sem fechamento.")
    return spans, warnings


def _parse_xml(data: bytes) -> etree._Element:
    parser = etree.XMLParser(
        no_network=True,
        recover=False,
        remove_blank_text=False,
        resolve_entities=False,
    )
    return etree.fromstring(data, parser=parser)


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(element.text or "" for element in paragraph.iter(TEXT_TAG))


def _analyze_docx(path: Path) -> DocxAnalysis:
    path = Path(path)
    if not path.is_file():
        raise ValueError("O modelo Word selecionado não está disponível.")

    signature = _document_signature(path)
    nodes: list[dict] = []
    slots: list[MiniBoxSlot] = []
    warnings: list[str] = []
    order = 0

    try:
        with zipfile.ZipFile(path, "r") as archive:
            part_names = sorted(
                (
                    name
                    for name in archive.namelist()
                    if CONTENT_PART_PATTERN.fullmatch(name)
                ),
                key=_content_part_sort_key,
            )
            if "word/document.xml" not in part_names:
                raise ValueError("O arquivo não possui uma estrutura DOCX válida.")

            for part_name in part_names:
                root = _parse_xml(archive.read(part_name))
                paragraphs = root.xpath(".//w:p", namespaces=NAMESPACES)
                for paragraph_index, paragraph in enumerate(paragraphs):
                    text = _paragraph_text(paragraph)
                    spans, paragraph_warnings = _root_brace_spans(text)
                    warnings.extend(
                        f"{part_name}, parágrafo {paragraph_index + 1}: {warning}"
                        for warning in paragraph_warnings
                    )

                    cursor = 0
                    fixed_index = 0
                    for marker_index, (start, end) in enumerate(spans):
                        if start > cursor:
                            nodes.append(
                                {
                                    "id": _node_id(
                                        signature,
                                        part_name,
                                        paragraph_index,
                                        "FIXED_TEXT",
                                        fixed_index,
                                    ),
                                    "type": "FIXED_TEXT",
                                    "content": text[cursor:start],
                                }
                            )
                            fixed_index += 1

                        node_id = _node_id(
                            signature,
                            part_name,
                            paragraph_index,
                            "MINI_BOX",
                            marker_index,
                        )
                        content = text[start + 1 : end - 1]
                        nodes.append(
                            {
                                "id": node_id,
                                "type": "MINI_BOX",
                                "content": content,
                                "order": order,
                            }
                        )
                        slots.append(
                            MiniBoxSlot(
                                id=node_id,
                                part=part_name,
                                paragraph_index=paragraph_index,
                                marker_index=marker_index,
                                start=start,
                                end=end,
                                content=content,
                                order=order,
                            )
                        )
                        order += 1
                        cursor = end

                    if cursor < len(text):
                        nodes.append(
                            {
                                "id": _node_id(
                                    signature,
                                    part_name,
                                    paragraph_index,
                                    "FIXED_TEXT",
                                    fixed_index,
                                ),
                                "type": "FIXED_TEXT",
                                "content": text[cursor:],
                            }
                        )
    except zipfile.BadZipFile as exc:
        raise ValueError("O arquivo selecionado não é um DOCX válido.") from exc
    except etree.XMLSyntaxError as exc:
        raise ValueError("O modelo Word possui XML inválido ou corrompido.") from exc

    return DocxAnalysis(
        signature=signature,
        nodes=tuple(nodes),
        slots=tuple(slots),
        warnings=tuple(warnings),
    )


def inspect_docx_structure(path: Path) -> dict:
    analysis = _analyze_docx(Path(path))
    return {
        "document_signature": analysis.signature,
        "nodes": [dict(node) for node in analysis.nodes],
        "mini_box_count": len(analysis.slots),
        "generated_table_block": {
            "id": GENERATED_TABLE_BLOCK_ID,
            "type": "GENERATED_TABLE",
            "content": "Tabela gerada da proposta",
        },
        "warnings": list(analysis.warnings),
    }


def _validated_order(analysis: DocxAnalysis, ordered_ids: object) -> list[str]:
    if not isinstance(ordered_ids, list) or not all(
        isinstance(node_id, str) and node_id for node_id in ordered_ids
    ):
        raise ValueError("A ordem dos blocos do modelo é inválida.")
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("A ordem dos blocos contém identificadores duplicados.")

    expected_ids = {slot.id for slot in analysis.slots}
    if len(ordered_ids) != len(analysis.slots) or set(ordered_ids) != expected_ids:
        raise ValueError(
            "A estrutura do modelo foi alterada. Reprocesse a proposta antes de gerar o arquivo."
        )
    return list(ordered_ids)


def validate_mini_box_order(path: Path, ordered_ids: object) -> list[str]:
    return _validated_order(_analyze_docx(Path(path)), ordered_ids)


def _validated_document_block_order(
    analysis: DocxAnalysis,
    ordered_ids: object,
) -> list[str]:
    if not isinstance(ordered_ids, list) or not all(
        isinstance(node_id, str) and node_id for node_id in ordered_ids
    ):
        raise ValueError("A ordem visual do documento é inválida.")
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("A ordem visual do documento contém blocos duplicados.")

    expected_ids = {slot.id for slot in analysis.slots}
    expected_ids.add(GENERATED_TABLE_BLOCK_ID)
    if len(ordered_ids) != len(expected_ids) or set(ordered_ids) != expected_ids:
        raise ValueError(
            "A estrutura do modelo foi alterada. Reprocesse a proposta antes de gerar o arquivo."
        )
    return list(ordered_ids)


def resolve_document_block_layout(
    path: Path,
    ordered_ids: object,
) -> DocumentBlockLayout:
    analysis = _analyze_docx(Path(path))
    validated_order = _validated_document_block_order(analysis, ordered_ids)
    table_order = validated_order.index(GENERATED_TABLE_BLOCK_ID)
    mini_box_order = tuple(
        node_id
        for node_id in validated_order
        if node_id != GENERATED_TABLE_BLOCK_ID
    )

    target_paragraph_index = None
    if table_order < len(analysis.slots):
        target_slot = analysis.slots[table_order]
        if target_slot.part != "word/document.xml":
            raise ValueError(
                "A tabela gerada só pode ser posicionada no corpo principal do documento."
            )
        if table_order > 0:
            previous_slot = analysis.slots[table_order - 1]
            if (
                previous_slot.part == target_slot.part
                and previous_slot.paragraph_index == target_slot.paragraph_index
            ):
                raise ValueError(
                    "A tabela não pode ser inserida entre mini-boxes do mesmo parágrafo. "
                    "Posicione-a antes ou depois desse conjunto."
                )
        target_paragraph_index = target_slot.paragraph_index

    return DocumentBlockLayout(
        order=tuple(validated_order),
        mini_box_order=mini_box_order,
        table_paragraph_index=target_paragraph_index,
    )


def validate_document_block_order(path: Path, ordered_ids: object) -> list[str]:
    return list(resolve_document_block_layout(path, ordered_ids).order)


def _set_text(element: etree._Element, value: str) -> None:
    element.text = value
    if value[:1].isspace() or value[-1:].isspace():
        element.set(XML_SPACE, "preserve")
    else:
        element.attrib.pop(XML_SPACE, None)


def _replace_text_range(
    paragraph: etree._Element,
    start: int,
    end: int,
    replacement: str,
) -> None:
    text_elements = list(paragraph.iter(TEXT_TAG))
    texts = [element.text or "" for element in text_elements]
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for text in texts:
        ranges.append((cursor, cursor + len(text)))
        cursor += len(text)

    touched = [
        index
        for index, (node_start, node_end) in enumerate(ranges)
        if node_end > start and node_start < end
    ]
    if not touched:
        raise ValueError("Não foi possível localizar um bloco no XML do modelo.")

    first = touched[0]
    last = touched[-1]
    first_start = ranges[first][0]
    last_start = ranges[last][0]
    prefix = texts[first][: start - first_start]
    suffix = texts[last][end - last_start :]

    if first == last:
        _set_text(text_elements[first], prefix + replacement + suffix)
        return

    _set_text(text_elements[first], prefix + replacement)
    for index in touched[1:-1]:
        _set_text(text_elements[index], "")
    _set_text(text_elements[last], suffix)


def _rewrite_part(
    data: bytes,
    slots: list[MiniBoxSlot],
    replacement_contents: dict[str, str],
) -> bytes:
    root = _parse_xml(data)
    paragraphs = root.xpath(".//w:p", namespaces=NAMESPACES)
    by_paragraph: dict[int, list[MiniBoxSlot]] = {}
    for slot in slots:
        by_paragraph.setdefault(slot.paragraph_index, []).append(slot)

    for paragraph_index, paragraph_slots in by_paragraph.items():
        if paragraph_index >= len(paragraphs):
            raise ValueError("A estrutura interna do modelo foi alterada durante a geração.")
        paragraph = paragraphs[paragraph_index]
        for slot in sorted(paragraph_slots, key=lambda item: item.start, reverse=True):
            _replace_text_range(
                paragraph,
                slot.start,
                slot.end,
                "{" + replacement_contents[slot.id] + "}",
            )

    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        standalone=True,
    )


def rebuild_docx_with_mini_box_order(
    source_path: Path,
    target_path: Path,
    ordered_ids: object,
) -> None:
    source_path = Path(source_path)
    target_path = Path(target_path)
    analysis = _analyze_docx(source_path)
    validated_order = _validated_order(analysis, ordered_ids)
    slots_by_id = {slot.id: slot for slot in analysis.slots}
    replacement_contents = {
        target_slot.id: slots_by_id[source_id].content
        for target_slot, source_id in zip(analysis.slots, validated_order)
    }
    slots_by_part: dict[str, list[MiniBoxSlot]] = {}
    for slot in analysis.slots:
        slots_by_part.setdefault(slot.part, []).append(slot)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.stem}_",
        suffix=".docx",
        dir=target_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(source_path, "r") as source_archive:
            with zipfile.ZipFile(temporary_path, "w") as target_archive:
                for entry in source_archive.infolist():
                    data = source_archive.read(entry.filename)
                    if entry.filename in slots_by_part:
                        data = _rewrite_part(
                            data,
                            slots_by_part[entry.filename],
                            replacement_contents,
                        )
                    target_archive.writestr(entry, data)
        os.replace(temporary_path, target_path)
    finally:
        temporary_path.unlink(missing_ok=True)
