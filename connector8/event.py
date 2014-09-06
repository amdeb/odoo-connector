# -*- coding: utf-8 -*-

from collections import Callable


class Event(object):
    """ An event contains consumers called when the event is fired.

    The events are able to filter the consumers to execute by model name.

    The usage of an event is to instantiate an `Event` object::

        on_my_event = Event()

    An event always have at least the 2 following arguments:

    * session
    * model_name

    Then to subscribe one or more consumers, a consumer is a function::

        def do_something(session, model_name, a, b):
            print "Event was fired with arguments: %s, %s" % (a, b)

        # active on all models
        on_my_event.subscribe(do_something)

        def do_something_product(session, model_name, a, b):
            print ("Event was fired on a product "
                   "with arguments: %s, %s" % (a, b))

        # active only on product.product
        on_my_event.subscribe(do_something_product,
                              model_names='product.product')

    We can also replace an event::

        def do_something_product2(session, model_name, a, b):
            print "Consumer 2"
            print ("Event was fired on a product "
                  "with arguments: %s, %s" % (a, b))

        on_my_event.subscribe(do_something_product2,
                              replacing=do_something_product)

    Finally, we fire the event::

        on_my_event.fire(session, 'res.users', 'value_a', 'value_b')

    A consumer can be subscribed using a decorator::

        @on_my_event
        def do_other_thing(session, model_name, a, b):
            print 'foo'

        @on_my_event(replacing=do_other_thing)
        def print_bar(session, model_name, a, b):
            print 'bar'

    """

    def __init__(self):
        """

        :type self: object
        """
        self._consumers = {None: set()}

    def subscribe(self, consumer, model_names=None, replacing=None):
        """ Subscribe a consumer on the event

        :param consumer: the function to register on the event
        :param model_names: the consumer will be active only on these models,
            active on all models if ``None``
        :param replacing: the function being replaced by this new one.
        """
        if replacing is not None:
            self.unsubscribe(replacing, model_names=model_names)
        if not hasattr(model_names, '__iter__'):
            model_names = [model_names]
        for name in model_names:
            self._consumers.setdefault(name, set()).add(consumer)

    def unsubscribe(self, consumer, model_names=None):
        """ Remove a consumer from the event

        :param consumer: the function to unsubscribe
        :param model_names: remove only for these models or remove a
            consumer which is active on all models if ``None``.
        """
        if not hasattr(model_names, '__iter__'):
            model_names = [model_names]
        for name in model_names:
            if name in self._consumers:
                self._consumers[name].discard(consumer)

    def has_consumer_for(self, session, model_name):
        """ Return True if at least one consumer is registered
        for the model.
        """
        if len(self._consumers.get(None, set())) > 0:
            return True  # at least 1 global consumer exist
        return len(self._consumers.get(model_name, set())) > 0

    def fire(self, session, model_name, *args, **kwargs):
        """ Call each consumer subscribed on the event with the given
        arguments and keyword arguments.

        All the consumers which were subscribed globally (no model name) or
        which are subscribed on the same model

        :param session: current session
        :type session: :py:class:`connector.session.Session`
        :param model_name: name of the model
        :type model_name: str
        :param args: arguments propagated to the consumer
                     The second argument of `args` is the model name.
                     The first argument is the session.
        :param kwargs: keyword arguments propagated to the consumer
        """
        assert isinstance(model_name, basestring), (
            "Second argument must be the model name as string, "
            "instead received: %s" % model_name)

        args = tuple([session, model_name] + list(args))
        for name in (None, model_name):
            for consumer in self._consumers.get(name, set()):
                consumer(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """ Event decorator

        For an event ``on_event`` declared like this::

            on_event = Event()

        A consumer can be subscribed using::

            @on_event
            def do_things(arg1, arg2):
                # work

        And for consumers specific to models::

            @on_event(model_names=['product.product', 'res.partner'])
            def do_things(arg1, arg2):
                # work

        The accepted arguments are those of :meth:`subscribe`.
        """
        def with_subscribe(**opts):
            def wrapped_func(func):
                self.subscribe(func, **opts)
                return func
            return wrapped_func

        if len(args) == 1 and isinstance(args[0], Callable):
            return with_subscribe(**kwargs)(*args)
        return with_subscribe(**kwargs)


on_record_write = Event()
"""
``on_record_write`` is fired when one record has been updated.

Listeners should take the following arguments:

 * session: :py:class:`~connector.session.ConnectorSession` object
 * model_name: name of the model
 * record_id: id of the record
 * vals:  field values of the new record, e.g {'field_name': field_value, ...}

"""

on_record_create = Event()
"""
``on_record_create`` is fired when one record has been created.

Listeners should take the following arguments:

 * session: :py:class:`~connector.session.ConnectorSession` object
 * model_name: name of the model
 * record_id: id of the created record
 * vals:  field values updated, e.g {'field_name': field_value, ...}

"""

on_record_unlink = Event()
"""
``on_record_unlink`` is fired when one record has been deleted.

Listeners should take the following arguments:

 * session: :py:class:`~connector.session.ConnectorSession` object
 * model_name: name of the model
 * record_id: id of the record

"""
