from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _TableChain:
    def __init__(self, execute_results: list[object] | None = None):
        self._execute_results = list(execute_results or [])
        self.update_payload: dict | None = None
        self.mode: str | None = None

    def select(self, *_args, **_kwargs):
        self.mode = 'select'
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def update(self, payload: dict):
        self.mode = 'update'
        self.update_payload = payload
        return self

    def single(self):
        return self

    def execute(self):
        if self._execute_results:
            return self._execute_results.pop(0)
        return SimpleNamespace(data=[])


class _SupabaseMock:
    def __init__(self, suggestion_row: dict, user_row: dict | None = None, updated_row: dict | None = None):
        self.suggestion_select_results = [SimpleNamespace(data=[suggestion_row])]
        self.suggestion_update_results = [
            SimpleNamespace(data=[{
                **suggestion_row,
                'paperclip_issue_id': (updated_row or suggestion_row).get('paperclip_issue_id'),
                'paperclip_issue_identifier': (updated_row or suggestion_row).get('paperclip_issue_identifier'),
                'paperclip_issue_url': (updated_row or suggestion_row).get('paperclip_issue_url'),
            }]),
            SimpleNamespace(data=[updated_row or suggestion_row]),
        ]
        self.suggestion_update_payloads: list[dict] = []
        self.users_table = _TableChain([SimpleNamespace(data=[user_row] if user_row else [])])

    def table(self, name: str):
        if name == 'outreach_suggestions':
            parent = self

            class _SuggestionTable(_TableChain):
                def select(self, *_args, **_kwargs):
                    self.mode = 'select'
                    return self

                def update(self, payload: dict):
                    self.mode = 'update'
                    self.update_payload = payload
                    parent.suggestion_update_payloads.append(payload)
                    return self

                def execute(self):
                    if self.mode == 'select':
                        return parent.suggestion_select_results.pop(0)
                    if self.mode == 'update':
                        return parent.suggestion_update_results.pop(0)
                    return SimpleNamespace(data=[])

            return _SuggestionTable()
        if name == 'users':
            return self.users_table
        raise AssertionError(f'unexpected table {name}')


@pytest.fixture()
def client():
    from app.routers import suggestions as suggestions_router
    from app.deps import get_current_user

    app = FastAPI()
    app.include_router(suggestions_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='user-1')
    return TestClient(app)


def test_approve_suggestion_creates_paperclip_issue(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'draft_message': 'Would love to reconnect.',
        'trigger_summary': 'New funding round',
        'paperclip_issue_id': None,
        'contact': {'name': 'Jane Doe'},
    }
    updated_row = {
        **suggestion_row,
        'status': 'approved',
        'paperclip_issue_id': 'issue-123',
        'paperclip_issue_identifier': 'PAP-42',
        'paperclip_issue_url': 'https://paperclip.example/issues/issue-123',
    }
    supabase_mock = _SupabaseMock(
        suggestion_row=suggestion_row,
        user_row={'paperclip_company_id': 'company-123'},
        updated_row=updated_row,
    )

    with (
        patch('app.routers.suggestions.supabase', supabase_mock),
        patch('app.routers.suggestions.create_outreach_issue', AsyncMock(return_value={
            'issue_id': 'issue-123',
            'issue_identifier': 'PAP-42',
            'issue_url': 'https://paperclip.example/issues/issue-123',
        })),
    ):
        response = client.put('/suggestions/sug-1', json={'status': 'approved'})

    assert response.status_code == 200
    body = response.json()
    assert body['paperclip_issue_id'] == 'issue-123'
    assert supabase_mock.suggestion_update_payloads == [
        {
            'paperclip_issue_id': 'issue-123',
            'paperclip_issue_identifier': 'PAP-42',
            'paperclip_issue_url': 'https://paperclip.example/issues/issue-123',
        },
        {'status': 'approved'},
    ]


def test_approve_suggestion_reuses_existing_issue(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'paperclip_issue_id': 'issue-existing',
        'paperclip_issue_identifier': 'PAP-7',
        'paperclip_issue_url': 'https://paperclip.example/issues/issue-existing',
        'contact': {'name': 'Jane Doe'},
    }
    updated_row = {**suggestion_row, 'status': 'approved'}
    supabase_mock = _SupabaseMock(suggestion_row=suggestion_row, updated_row=updated_row)
    create_issue = AsyncMock()

    with (
        patch('app.routers.suggestions.supabase', supabase_mock),
        patch('app.routers.suggestions.create_outreach_issue', create_issue),
    ):
        response = client.put('/suggestions/sug-1', json={'status': 'approved'})

    assert response.status_code == 200
    create_issue.assert_not_awaited()
    assert supabase_mock.suggestion_update_payloads == [{'status': 'approved'}]


def test_approve_suggestion_without_company_returns_422(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'paperclip_issue_id': None,
        'contact': {'name': 'Jane Doe'},
    }
    supabase_mock = _SupabaseMock(suggestion_row=suggestion_row)

    with patch('app.routers.suggestions.supabase', supabase_mock):
        response = client.put('/suggestions/sug-1', json={'status': 'approved'})

    assert response.status_code == 422
    assert 'complete onboarding first' in response.json()['detail']


def test_approve_suggestion_paperclip_failure_returns_502(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'paperclip_issue_id': None,
        'contact': {'name': 'Jane Doe'},
    }
    supabase_mock = _SupabaseMock(
        suggestion_row=suggestion_row,
        user_row={'paperclip_company_id': 'company-123'},
    )

    with (
        patch('app.routers.suggestions.supabase', supabase_mock),
        patch('app.routers.suggestions.create_outreach_issue', AsyncMock(side_effect=RuntimeError('boom'))),
    ):
        response = client.put('/suggestions/sug-1', json={'status': 'approved'})

    assert response.status_code == 502
    assert 'Could not create review issue in Paperclip' in response.json()['detail']


def test_approve_suggestion_persist_empty_result_returns_do_not_retry(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'paperclip_issue_id': None,
        'contact': {'name': 'Jane Doe'},
    }
    supabase_mock = _SupabaseMock(
        suggestion_row=suggestion_row,
        user_row={'paperclip_company_id': 'company-123'},
    )
    supabase_mock.suggestion_update_results = [SimpleNamespace(data=[])]

    with (
        patch('app.routers.suggestions.supabase', supabase_mock),
        patch('app.routers.suggestions.create_outreach_issue', AsyncMock(return_value={
            'issue_id': 'issue-123',
            'issue_identifier': 'PAP-42',
            'issue_url': 'https://paperclip.example/issues/issue-123',
        })),
    ):
        response = client.put('/suggestions/sug-1', json={'status': 'approved'})

    assert response.status_code == 502
    assert 'do not retry' in response.json()['detail']


def test_dismiss_suggestion_does_not_create_issue(client: TestClient):
    suggestion_row = {
        'id': 'sug-1',
        'user_id': 'user-1',
        'subject': 'Catch up with GC',
        'paperclip_issue_id': None,
        'contact': {'name': 'Jane Doe'},
    }
    updated_row = {**suggestion_row, 'status': 'dismissed'}
    supabase_mock = _SupabaseMock(suggestion_row=suggestion_row, updated_row=updated_row)
    create_issue = AsyncMock()

    with (
        patch('app.routers.suggestions.supabase', supabase_mock),
        patch('app.routers.suggestions.create_outreach_issue', create_issue),
    ):
        response = client.put('/suggestions/sug-1', json={'status': 'dismissed'})

    assert response.status_code == 200
    create_issue.assert_not_awaited()
    assert supabase_mock.suggestion_update_payloads == [{'status': 'dismissed'}]


@pytest.mark.asyncio
async def test_create_outreach_issue_uses_issue_api_shape():
    from app.services import paperclip

    http_client = AsyncMock()
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        'id': 'issue-123',
        'identifier': 'PAP-42',
        'url': 'https://paperclip.example/issues/issue-123',
    }
    http_client.post.return_value = response

    with patch('app.services.paperclip.httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=http_client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await paperclip.create_outreach_issue(
            'company-123',
            {
                'id': 'sug-1',
                'subject': 'Catch up with GC',
                'draft_message': 'Would love to reconnect.',
                'trigger_summary': 'New funding round',
                'signal_id': 'signal-9',
                'contact': {'name': 'Jane Doe'},
            },
        )

    assert result == {
        'issue_id': 'issue-123',
        'issue_identifier': 'PAP-42',
        'issue_url': 'https://paperclip.example/issues/issue-123',
    }
    http_client.post.assert_awaited_once()
    _, kwargs = http_client.post.await_args
    assert kwargs['json']['title'] == 'Review outreach: Catch up with GC'
    assert kwargs['json']['description'].startswith('**Why now:** New funding round')
    assert kwargs['json']['status'] == 'todo'
    assert kwargs['json']['priority'] == 'high'
