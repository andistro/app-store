function doSearch() {
    let term = document.getElementById('search').value;
    if (term.length > 0)
        window.location.href = "software-store://pkg?search=" + encodeURIComponent(term);
}
document.getElementById('search').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') doSearch();
});

function updateProgress(percent) {
    let pb = document.getElementById('progress-bar');
    if (pb) {
        pb.innerHTML = '<div class="progress" style="width:'+Math.round(percent*100)+'%"></div>';
    }
}