from dockerctx import new_container


def test_command():
    with new_container(
            image_name='alpine:latest',
            command='echo "hey"',
            docker_api_version='1.24') as container:
        for line in container.logs(stream=True):
            assert line == b'hey\n'
            break

