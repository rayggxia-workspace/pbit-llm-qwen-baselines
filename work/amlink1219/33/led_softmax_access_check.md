# Direct Ising SoftMax paper: metadata and access check

Checked 2026-10-18. Existing Zotero item supplied by parent: 7QSGIULK. No Zotero writes performed by this subagent.

**Energy-Efficient Parallel Ising SoftMax Engine for Transformer Attention Based on Asynchronous SOT-P-Bits.** Yu Liu; Bolin Zhang; Jialiang Yin; Wentao Huang; Zhenyu Guan; Weisheng Zhao; Deming Zhang; Lang Zeng. IEEE Electron Device Letters **47(7), 1458-1461, July 2026**. DOI **10.1109/LED.2026.3691358**.

- [Official article](https://ieeexplore.ieee.org/document/11515117/)
- [DOI](https://doi.org/10.1109/LED.2026.3691358)
- [Crossref metadata API](https://api.crossref.org/works/10.1109%2FLED.2026.3691358)
- [OpenAlex record](https://openalex.org/W7160920321)

Current issue/volume/pages and all eight authors were read from the live Crossref record. The old ResearchGate January/PP(99):1-1 listing is an early metadata snapshot, not the current issue assignment.

**Full text was not obtained.** Official IEEE landing page returned a JavaScript/bot-verification page through the web tool. Official stamp and direct PDF requests did not return a usable PDF. Crossref's registered PDF link `https://xplorestaging.ieee.org/ielx8/55/11589473/11515117.pdf?arnumber=11515117` returned HTTP 200 but `text/html; charset=UTF-8`, 48528 bytes, beginning `<!DOCTYPE html>`; this is article/abstract HTML, not a PDF. It was not saved as a PDF. The public OpenAlex API returned `is_oa=false`, `oa_status=closed`, `oa_url=null`, `best_oa_location=null`, `any_repository_has_fulltext=false`. Exact title plus author/institution/arXiv/TechRxiv/ResearchSquare searches did not locate an open author manuscript. ResearchGate currently says request full text, not a hosted PDF. No author was contacted and no access controls were bypassed.

Reading scope is **metadata and abstract only**. The abstract describes an asynchronous SOT-MTJ p-bit SoftMax-to-Ising mapping. Its claim about FP16-level precision at 32us was not checked against the paper's definitions, vector sizes, counts, measurement/simulation split or full hardware boundary, so it is **not used as quantitative evidence**. Sampling output versus a complete probability vector, mixing/correlation, bias-configuration cost, readout and end-to-end accuracy/PPA remain unknown pending the four-page paper and any supplement.

This paper is a directly relevant priority retrieval item; lack of accessible full text should be explicit in the literature review. It does not alter the experimentally proposed need for a matched digital stable-Softmax baseline and a digital systematic sampler baseline.
