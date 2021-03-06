import pendulum
import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

from share.models import ShareUser, SourceConfig
from share.tasks import HarvesterTask, NormalizerTask


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Harvest from all SourceConfigs')
        parser.add_argument('--force', action='store_true', help='Force the harvest task to run against all odds')
        parser.add_argument('--ignore-disabled', action='store_true', help='Allow disabled SourceConfigs to run')
        parser.add_argument('source-config', nargs='*', type=str, help='The name of the SourceConfig to harvest from')
        parser.add_argument('--async', action='store_true', help='Whether or not to use Celery')

        parser.add_argument('--days-back', type=int, help='The number of days to go back, defaults to 1')
        parser.add_argument('--start', type=str, help='The day to start harvesting, in the format YYYY-MM-DD')
        parser.add_argument('--end', type=str, help='The day to end harvesting, in the format YYYY-MM-DD')
        parser.add_argument('--limit', type=int, help='The maximum number of works to harvest, defaults to no limit')

        parser.add_argument('--ids', nargs='*', type=str, help='Harvest specific works by identifier, instead of by date range.')
        parser.add_argument('--set-spec', type=str, help='Filter harvested works by OAI setSpecs')

    def handle(self, *args, **options):
        user = ShareUser.objects.get(username=settings.APPLICATION_USERNAME)

        if options['ids']:
            self.harvest_ids(user, options)
            return

        task_kwargs = {'force': options.get('force', False), 'ignore_disabled': options.get('ignore_disabled', False)}

        if options['days_back'] is not None and (options['start'] or options['end']):
            self.stdout.write('Please choose days-back OR a start date with end date, not both')
            return

        if options['days_back'] is not None:
            task_kwargs['end'] = datetime.datetime.utcnow() + datetime.timedelta(days=-(options['days_back'] - 1))
            task_kwargs['start'] = datetime.datetime.utcnow() + datetime.timedelta(days=-options['days_back'])
        else:
            task_kwargs['start'] = pendulum.parse(options['start']) if options.get('start') else pendulum.utcnow() - datetime.timedelta(days=int(options['days_back'] or 1))
            task_kwargs['end'] = pendulum.parse(options['end']) if options.get('end') else pendulum.utcnow()

        task_kwargs['end'] = task_kwargs['end'].isoformat()
        task_kwargs['start'] = task_kwargs['start'].isoformat()

        if options['limit'] is not None:
            task_kwargs['limit'] = options['limit']

        if options['set_spec']:
            task_kwargs['set_spec'] = options['set_spec']

        if not options['source-config'] and options['all']:
            options['source-config'] = SourceConfig.objects.filter(disabled=False).values_list('label', flat=True)

        for label in options['source-config']:
            assert SourceConfig.objects.filter(label=label).exists()

            task_args = (user.id, label,)
            if options['async']:
                HarvesterTask().apply_async(task_args, task_kwargs)
                self.stdout.write('Started harvest job for source config {}'.format(label))
            else:
                self.stdout.write('Running harvester for {}'.format(label))
                HarvesterTask().apply(task_args, task_kwargs, throw=True)

    def harvest_ids(self, user, options):
        if len(options['source-config']) != 1:
            self.stdout.write('When harvesting by ID, only one harvester at a time, please.')
            return
        self.stdout.write('Harvesting documents by ID...')
        label = options['source-config'][0]
        config = SourceConfig.objects.get(label=label)
        harvester = config.get_harvester()
        for id in options['ids']:
            raw = harvester.harvest_by_id(id)
            task = NormalizerTask().apply_async((user.id, config.label, raw.id,))
            self.stdout.write('Raw data {} harvested from {}, saved as {}. Started normalizer task {}.'.format(id, config.label, raw.id, task))
