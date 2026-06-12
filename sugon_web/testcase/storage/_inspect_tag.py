import pytest

def test_router_push_tag(page):
    page.goto("https://172.22.1.190:30000/oss/#/bucket-list-page-detail/autotest-g0up7")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)
    
    print(f"\n=== Initial URL: {page.url} ===")
    
    # Use Vue router to push to tag page
    page.evaluate("""
        () => {
            const container = document.querySelector('.bucket-detail-container');
            let vue = container.__vue__;
            if (!vue) {
                for (const child of container.querySelectorAll('*')) {
                    if (child.__vue__) { vue = child.__vue__; break; }
                }
            }
            if (vue && vue.$router) {
                vue.$router.push('/bucket-list-page-detail/autotest-g0up7/basicconfig/tag');
                return 'pushed';
            }
            return 'no router';
        }
    """)
    
    page.wait_for_timeout(5000)
    print(f"=== URL after push: {page.url} ===")
    
    # Check for tag elements
    for text in ["标签键", "标签值", "添加标签", "暂无数据"]:
        els = page.get_by_text(text).all()
        print(f"get_by_text('{text}'): {len(els)}")
    
    # Check tables
    tables = page.locator(".el-table").all()
    print(f"Tables: {len(tables)}")
    for i, table in enumerate(tables):
        rows = table.locator(".el-table__body-wrapper tr").all()
        print(f"  Table {i}: {len(rows)} rows")
        for j, row in enumerate(rows[:3]):
            cells = row.locator("td").all()
            cell_texts = [c.inner_text().strip() for c in cells]
            print(f"    Row {j}: {cell_texts}")
