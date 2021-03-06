# -*- coding: utf8 -*-
# This file is part of PyBossa.
#
# Copyright (C) 2014 SF Isle of Man Limited
#
# PyBossa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyBossa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PyBossa.  If not, see <http://www.gnu.org/licenses/>.
import copy
import json
from collections import namedtuple
from mock import patch, Mock
from nose.tools import assert_raises
from pybossa.importers import (_BulkTaskFlickrImport, _BulkTaskCSVImport,
    _BulkTaskGDImport, _BulkTaskEpiCollectPlusImport, BulkImportException,
    Importer)

from default import Test
from factories import AppFactory, TaskFactory
from pybossa.repositories import TaskRepository
from pybossa.core import db
task_repo = TaskRepository(db)



@patch.object(Importer, '_create_importer_for')
class TestImporterPublicMethods(Test):
    importer = Importer()

    def test_create_tasks_creates_them_correctly(self, importer_factory):
        mock_importer = Mock()
        mock_importer.tasks.return_value = [{'info': {'question': 'question',
                                                     'url': 'url'},
                                            'n_answers': 20}]
        importer_factory.return_value = mock_importer
        app = AppFactory.create()
        form_data = dict(type='csv', csv_url='http://fakecsv.com')
        self.importer.create_tasks(task_repo, app.id, **form_data)
        task = task_repo.get_task(1)

        assert task is not None
        assert task.app_id == app.id, task.app_id
        assert task.n_answers == 20, task.n_answers
        assert task.info == {'question': 'question', 'url': 'url'}, task.info
        importer_factory.assert_called_with('csv')
        mock_importer.tasks.assert_called_with(**form_data)


    def test_create_tasks_creates_many_tasks(self, importer_factory):
        mock_importer = Mock()
        mock_importer.tasks.return_value = [{'info': {'question': 'question1'}},
                                            {'info': {'question': 'question2'}}]
        importer_factory.return_value = mock_importer
        app = AppFactory.create()
        form_data = dict(type='gdocs', googledocs_url='http://ggl.com')
        result = self.importer.create_tasks(task_repo, app.id, **form_data)
        tasks = task_repo.filter_tasks_by(app_id=app.id)

        assert len(tasks) == 2, len(tasks)
        assert result == '2 new tasks were imported successfully', result
        importer_factory.assert_called_with('gdocs')


    def test_create_tasks_not_creates_duplicated_tasks(self, importer_factory):
        mock_importer = Mock()
        mock_importer.tasks.return_value = [{'info': {'question': 'question'}}]
        importer_factory.return_value = mock_importer
        app = AppFactory.create()
        TaskFactory.create(app=app, info={'question': 'question'})
        form_data = dict(type='flickr', album_id='1234')

        result = self.importer.create_tasks(task_repo, app.id, **form_data)
        tasks = task_repo.filter_tasks_by(app_id=app.id)

        assert len(tasks) == 1, len(tasks)
        assert result == 'It looks like there were no new records to import', result
        importer_factory.assert_called_with('flickr')


    def test_count_tasks_to_import_returns_what_expected(self, importer_factory):
        mock_importer = Mock()
        mock_importer.count_tasks.return_value = 2
        importer_factory.return_value = mock_importer
        form_data = dict(type='epicollect', epicollect_project='project',
                         epicollect_form='form')

        number_of_tasks = self.importer.count_tasks_to_import(**form_data)

        assert number_of_tasks == 2, number_of_tasks
        importer_factory.assert_called_with('epicollect')


    def test_get_all_importer_names_returns_default_importer_names(self, create):
        importers = self.importer.get_all_importer_names()
        expected_importers = ['csv', 'gdocs', 'epicollect']

        assert set(importers) == set(expected_importers)


    def test_get_all_importers_returns_configured_importers(self, create):
        importer_params = {'api_key': self.flask_app.config['FLICKR_API_KEY']}
        importer = Importer()
        importer.register_flickr_importer(importer_params)

        assert 'flickr' in importer.get_all_importer_names()



@patch('pybossa.importers.requests')
class Test_BulkTaskFlickrImport(object):

    invalid_response = {u'stat': u'fail',
                        u'code': 1, u'message': u'Photoset not found'}
    response = {
        u'stat': u'ok',
        u'photoset': {
            u'perpage': 500,
            u'title': u'Science Hack Day Balloon Mapping Workshop',
            u'photo': [
                {u'isfamily': 0, u'title': u'Inflating the balloon', u'farm': 6,
                 u'ispublic': 1, u'server': u'5441', u'isfriend': 0,
                 u'secret': u'00e2301a0d', u'isprimary': u'0', u'id': u'8947115130'},
                {u'isfamily': 0, u'title': u'Inflating the balloon', u'farm': 4,
                 u'ispublic': 1, u'server': u'3763', u'isfriend': 0,
                 u'secret': u'70d482fc68', u'isprimary': u'0', u'id': u'8946490553'},
                {u'isfamily': 0, u'title': u'Inflating the balloon', u'farm': 3,
                 u'ispublic': 1, u'server': u'2810', u'isfriend': 0,
                 u'secret': u'99cae13d87', u'isprimary': u'0', u'id': u'8947113960'}],
            u'pages': 1,
            u'primary': u'8947113500',
            u'id': u'72157633923521788',
            u'ownername': u'Teleyinex',
            u'owner': u'32985084@N00',
            u'per_page': 500,
            u'total': u'3',
            u'page': 1}}
    photo = {u'isfamily': 0, u'title': u'Inflating the balloon', u'farm': 6,
             u'ispublic': 1, u'server': u'5441', u'isfriend': 0,
             u'secret': u'00e2301a0d', u'isprimary': u'0', u'id': u'8947115130'}
    importer = _BulkTaskFlickrImport(api_key='fake-key')


    def make_response(self, text, status_code=200):
        fake_response = Mock()
        fake_response.text = text
        fake_response.status_code = status_code
        return fake_response


    def test_call_to_flickr_api_endpoint(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.response))
        self.importer._get_album_info('72157633923521788')
        url = 'https://api.flickr.com/services/rest/'
        payload = {'method': 'flickr.photosets.getPhotos',
                   'api_key': 'fake-key',
                   'photoset_id': '72157633923521788',
                   'format': 'json',
                   'nojsoncallback': '1'}
        requests.get.assert_called_with(url, params=payload)


    def test_call_to_flickr_api_uses_no_credentials(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.response))
        self.importer._get_album_info('72157633923521788')

        # The request MUST NOT include user credentials, to avoid private photos
        url_call_params = requests.get.call_args_list[0][1]['params'].keys()
        assert 'auth_token' not in url_call_params


    def test_count_tasks_returns_number_of_photos_in_album(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.response))

        number_of_tasks = self.importer.count_tasks(album_id='72157633923521788')

        assert number_of_tasks is 3, number_of_tasks


    def test_count_tasks_raises_exception_if_invalid_album(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.invalid_response))

        assert_raises(BulkImportException, self.importer.count_tasks, album_id='bad')


    def test_count_tasks_raises_exception_on_non_200_flckr_response(self, requests):
        requests.get.return_value = self.make_response('Not Found', 404)

        assert_raises(BulkImportException, self.importer.count_tasks,
                      album_id='72157633923521788')


    def test_tasks_returns_list_of_all_photos(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.response))

        photos = self.importer.tasks(album_id='72157633923521788')

        assert len(photos) == 3, len(photos)


    def test_tasks_returns_tasks_with_title_and_url_info_fields(self, requests):
        task_data_info_fields = ['url', 'title']
        requests.get.return_value = self.make_response(json.dumps(self.response))
        url = 'https://farm6.staticflickr.com/5441/8947115130_00e2301a0d.jpg'
        url_m = 'https://farm6.staticflickr.com/5441/8947115130_00e2301a0d_m.jpg'
        url_b = 'https://farm6.staticflickr.com/5441/8947115130_00e2301a0d_b.jpg'
        title = self.response['photoset']['photo'][0]['title']
        photo = self.importer.tasks(album_id='72157633923521788')[0]

        assert photo['info'].get('title') == title
        assert photo['info'].get('url') == url, photo['info'].get('url')
        assert photo['info'].get('url_m') == url_m, photo['info'].get('url_m')
        assert photo['info'].get('url_b') == url_b, photo['info'].get('url_b')


    def test_tasks_raises_exception_if_invalid_album(self, requests):
        requests.get.return_value = self.make_response(json.dumps(self.invalid_response))

        assert_raises(BulkImportException, self.importer.tasks, album_id='bad')


    def test_tasks_raises_exception_on_non_200_flckr_response(self, requests):
        requests.get.return_value = self.make_response('Not Found', 404)

        assert_raises(BulkImportException, self.importer.tasks,
                      album_id='72157633923521788')


    def test_tasks_returns_all_for_sets_with_more_than_500_photos(self, requests):
        # Deep-copy the object, as we will be modifying it and we don't want
        # these modifications to affect other tests
        first_response = copy.deepcopy(self.response)
        first_response['photoset']['pages'] = 2
        first_response['photoset']['total'] = u'600'
        first_response['photoset']['page'] = 1
        first_response['photoset']['photo'] = [self.photo for i in range(500)]
        second_response = copy.deepcopy(self.response)
        second_response['photoset']['pages'] = 2
        second_response['photoset']['total'] = u'600'
        second_response['photoset']['page'] = 2
        second_response['photoset']['photo'] = [self.photo for i in range(100)]
        fake_first_response = self.make_response(json.dumps(first_response))
        fake_second_response = self.make_response(json.dumps(second_response))
        responses = [fake_first_response, fake_second_response]
        requests.get.side_effect = lambda *args, **kwargs: responses.pop(0)

        photos = self.importer.tasks(album_id='72157633923521788')

        assert len(photos) == 600, len(photos)


    def test_tasks_returns_all_for_sets_with_more_than_1000_photos(self, requests):
        # Deep-copy the object, as we will be modifying it and we don't want
        # these modifications to affect other tests
        first_response = copy.deepcopy(self.response)
        first_response['photoset']['pages'] = 3
        first_response['photoset']['total'] = u'1100'
        first_response['photoset']['page'] = 1
        first_response['photoset']['photo'] = [self.photo for i in range(500)]
        second_response = copy.deepcopy(self.response)
        second_response['photoset']['pages'] = 3
        second_response['photoset']['total'] = u'1100'
        second_response['photoset']['page'] = 2
        second_response['photoset']['photo'] = [self.photo for i in range(500)]
        third_response = copy.deepcopy(self.response)
        third_response['photoset']['pages'] = 3
        third_response['photoset']['total'] = u'1100'
        third_response['photoset']['page'] = 3
        third_response['photoset']['photo'] = [self.photo for i in range(100)]
        fake_first_response = self.make_response(json.dumps(first_response))
        fake_second_response = self.make_response(json.dumps(second_response))
        fake_third_response = self.make_response(json.dumps(third_response))
        responses = [fake_first_response, fake_second_response, fake_third_response]
        requests.get.side_effect = lambda *args, **kwargs: responses.pop(0)

        photos = self.importer.tasks(album_id='72157633923521788')

        assert len(photos) == 1100, len(photos)



@patch('pybossa.importers.requests.get')
class Test_BulkTaskCSVImport(object):

    FakeRequest = namedtuple('FakeRequest', ['text', 'status_code', 'headers'])
    url = 'http://myfakecsvurl.com'
    importer = _BulkTaskCSVImport()


    def test_count_tasks_returns_0_if_no_rows_other_than_header(self, request):
        empty_file = self.FakeRequest('CSV,with,no,content\n', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        number_of_tasks = self.importer.count_tasks(csv_url=self.url)

        assert number_of_tasks is 0, number_of_tasks


    def test_count_tasks_returns_1_for_CSV_with_one_valid_row(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Baz\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        number_of_tasks = self.importer.count_tasks(csv_url=self.url)

        assert number_of_tasks is 1, number_of_tasks


    def test_count_tasks_raises_exception_if_file_forbidden(self, request):
        forbidden_request = self.FakeRequest('Forbidden', 403,
                                             {'content-type': 'text/csv'})
        request.return_value = forbidden_request
        msg = "Oops! It looks like you don't have permission to access that file"

        assert_raises(BulkImportException, self.importer.count_tasks, csv_url=self.url)
        try:
            self.importer.count_tasks(csv_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_raises_exception_if_not_CSV_file(self, request):
        html_request = self.FakeRequest('Not a CSV', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That file doesn't look like the right file."

        assert_raises(BulkImportException, self.importer.count_tasks, csv_url=self.url)
        try:
            self.importer.count_tasks(csv_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_raises_exception_if_dup_header(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Foo\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file
        msg = "The file you uploaded has two headers with the same name."

        assert_raises(BulkImportException, self.importer.count_tasks, csv_url=self.url)
        try:
            self.importer.count_tasks(csv_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_file_forbidden(self, request):
        forbidden_request = self.FakeRequest('Forbidden', 403,
                                             {'content-type': 'text/csv'})
        request.return_value = forbidden_request
        msg = "Oops! It looks like you don't have permission to access that file"

        assert_raises(BulkImportException, self.importer.tasks, csv_url=self.url)
        try:
            self.importer.tasks(csv_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_not_CSV_file(self, request):
        html_request = self.FakeRequest('Not a CSV', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That file doesn't look like the right file."

        assert_raises(BulkImportException, self.importer.tasks, csv_url=self.url)
        try:
            self.importer.tasks(csv_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_dup_header(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Foo\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file
        msg = "The file you uploaded has two headers with the same name."

        raised = False
        try:
            self.importer.tasks(csv_url=self.url).next()
        except BulkImportException as e:
            assert e[0] == msg, e
            raised = True
        finally:
            assert raised, "Exception not raised"


    def test_tasks_return_tasks_with_only_info_fields(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Baz\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        tasks = self.importer.tasks(csv_url=self.url)
        task = tasks.next()

        assert task == {"info": {u'Bar': u'2', u'Foo': u'1', u'Baz': u'3'}}, task


    def test_tasks_return_tasks_with_non_info_fields_too(self, request):
        empty_file = self.FakeRequest('Foo,Bar,priority_0\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        tasks = self.importer.tasks(csv_url=self.url)
        task = tasks.next()

        assert task == {'info': {u'Foo': u'1', u'Bar': u'2'},
                        u'priority_0': u'3'}, task



@patch('pybossa.importers.requests.get')
class Test_BulkTaskGDImport(object):

    FakeRequest = namedtuple('FakeRequest', ['text', 'status_code', 'headers'])
    url = 'http://drive.google.com'
    importer = _BulkTaskGDImport()


    def test_count_tasks_returns_0_if_no_rows_other_than_header(self, request):
        empty_file = self.FakeRequest('CSV,with,no,content\n', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        number_of_tasks = self.importer.count_tasks(googledocs_url=self.url)

        assert number_of_tasks is 0, number_of_tasks


    def test_count_tasks_returns_1_for_CSV_with_one_valid_row(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Baz\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        number_of_tasks = self.importer.count_tasks(googledocs_url=self.url)

        assert number_of_tasks is 1, number_of_tasks


    def test_count_tasks_raises_exception_if_file_forbidden(self, request):
        forbidden_request = self.FakeRequest('Forbidden', 403,
                                             {'content-type': 'text/plain'})
        request.return_value = forbidden_request
        msg = "Oops! It looks like you don't have permission to access that file"

        assert_raises(BulkImportException, self.importer.count_tasks, googledocs_url=self.url)
        try:
            self.importer.count_tasks(googledocs_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_raises_exception_if_not_CSV_file(self, request):
        html_request = self.FakeRequest('Not a CSV', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That file doesn't look like the right file."

        assert_raises(BulkImportException, self.importer.count_tasks, googledocs_url=self.url)
        try:
            self.importer.count_tasks(googledocs_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_raises_exception_if_dup_header(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Foo\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file
        msg = "The file you uploaded has two headers with the same name."

        assert_raises(BulkImportException, self.importer.count_tasks, googledocs_url=self.url)
        try:
            self.importer.count_tasks(googledocs_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_file_forbidden(self, request):
        forbidden_request = self.FakeRequest('Forbidden', 403,
                                             {'content-type': 'text/plain'})
        request.return_value = forbidden_request
        msg = "Oops! It looks like you don't have permission to access that file"

        assert_raises(BulkImportException, self.importer.tasks, googledocs_url=self.url)
        try:
            self.importer.tasks(googledocs_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_not_CSV_file(self, request):
        html_request = self.FakeRequest('Not a CSV', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That file doesn't look like the right file."

        assert_raises(BulkImportException, self.importer.tasks, googledocs_url=self.url)
        try:
            self.importer.tasks(googledocs_url=self.url)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_dup_header(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Foo\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file
        msg = "The file you uploaded has two headers with the same name."

        raised = False
        try:
            self.importer.tasks(googledocs_url=self.url).next()
        except BulkImportException as e:
            assert e[0] == msg, e
            raised = True
        finally:
            assert raised, "Exception not raised"


    def test_tasks_return_tasks_with_only_info_fields(self, request):
        empty_file = self.FakeRequest('Foo,Bar,Baz\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        tasks = self.importer.tasks(googledocs_url=self.url)
        task = tasks.next()

        assert task == {"info": {u'Bar': u'2', u'Foo': u'1', u'Baz': u'3'}}, task


    def test_tasks_return_tasks_with_non_info_fields_too(self, request):
        empty_file = self.FakeRequest('Foo,Bar,priority_0\n1,2,3', 200,
                                      {'content-type': 'text/plain'})
        request.return_value = empty_file

        tasks = self.importer.tasks(googledocs_url=self.url)
        task = tasks.next()

        assert task == {'info': {u'Foo': u'1', u'Bar': u'2'},
                        u'priority_0': u'3'}, task



@patch('pybossa.importers.requests.get')
class Test_BulkTaskEpiCollectPlusImport(object):

    FakeRequest = namedtuple('FakeRequest', ['text', 'status_code', 'headers'])
    epicollect = {'epicollect_project': 'fakeproject',
                  'epicollect_form': 'fakeform'}
    importer = _BulkTaskEpiCollectPlusImport()

    def test_count_tasks_raises_exception_if_file_forbidden(self, request):
        unauthorized_request = self.FakeRequest('Forbidden', 403,
                                           {'content-type': 'application/json'})
        request.return_value = unauthorized_request
        msg = "Oops! It looks like you don't have permission to access the " \
              "EpiCollect Plus project"

        assert_raises(BulkImportException, self.importer.count_tasks, **self.epicollect)
        try:
            self.importer.count_tasks(**self.epicollect)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_file_forbidden(self, request):
        unauthorized_request = self.FakeRequest('Forbidden', 403,
                                           {'content-type': 'application/json'})
        request.return_value = unauthorized_request
        msg = "Oops! It looks like you don't have permission to access the " \
              "EpiCollect Plus project"

        assert_raises(BulkImportException, self.importer.tasks, **self.epicollect)
        try:
            self.importer.tasks(**self.epicollect)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_raises_exception_if_not_json(self, request):
        html_request = self.FakeRequest('Not an application/json', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That project and form do not look like the right one."

        assert_raises(BulkImportException, self.importer.count_tasks, **self.epicollect)
        try:
            self.importer.count_tasks(**self.epicollect)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_tasks_raises_exception_if_not_json(self, request):
        html_request = self.FakeRequest('Not an application/json', 200,
                                        {'content-type': 'text/html'})
        request.return_value = html_request
        msg = "Oops! That project and form do not look like the right one."

        assert_raises(BulkImportException, self.importer.tasks, **self.epicollect)
        try:
            self.importer.tasks(**self.epicollect)
        except BulkImportException as e:
            assert e[0] == msg, e


    def test_count_tasks_returns_number_of_tasks_in_project(self, request):
        data = [dict(DeviceID=23), dict(DeviceID=24)]
        html_request = self.FakeRequest(json.dumps(data), 200,
                                       {'content-type': 'application/json'})
        request.return_value = html_request

        number_of_tasks = self.importer.count_tasks(**self.epicollect)

        assert number_of_tasks is 2, number_of_tasks


    def test_tasks_returns_tasks_in_project(self, request):
        data = [dict(DeviceID=23), dict(DeviceID=24)]
        html_request = self.FakeRequest(json.dumps(data), 200,
                                        {'content-type': 'application/json'})
        request.return_value = html_request

        task = self.importer.tasks(**self.epicollect).next()

        assert task == {'info': {u'DeviceID': 23}}, task
