from link_utils import classify_url, extract_query_params


def test_classify_url():
    # SimpCity
    assert classify_url('https://simpcity.cr/threads/example.12345') == 'SimpCity'
    assert classify_url('http://www.simpcity.cr/page-1') == 'SimpCity'
    assert classify_url('https://simpcity.cr') == 'SimpCity'

    # Imgur
    assert classify_url('https://imgur.com/a/12345') == 'Imgur'
    assert classify_url('http://www.imgur.com/image.jpg') == 'Imgur'
    assert classify_url('https://imgur.com') == 'Imgur'

    # ImageBam
    assert classify_url('https://www.imagebam.com/view/12345') == 'ImageBam'
    assert classify_url('http://imagebam.com/gallery/abcde') == 'ImageBam'

    # CyberDrop
    assert classify_url('https://cyberdrop.me/a/12345') == 'CyberDrop'

    # Unknown
    assert classify_url('https://google.com') == 'Unknown'
    assert classify_url('https://unknown-host.net/images/1') == 'Unknown'
    assert classify_url('ftp://simpcity.cr/files') == 'Unknown'


def test_extract_query_params():
    # Single param
    assert extract_query_params('https://example.com/page?id=123') == {'id': '123'}

    # Multiple params
    assert extract_query_params('https://simpcity.cr/threads?page=2&sort=desc') == {'page': '2', 'sort': 'desc'}

    # No params
    assert extract_query_params('https://simpcity.cr/threads') == {}

    # URL encoded params
    assert extract_query_params('https://example.com/?q=hello+world&lang=en') == {'q': 'hello world', 'lang': 'en'}
